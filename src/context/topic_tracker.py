# -*- coding: utf-8 -*-
"""Rastreamento de tópicos recentes da conversa da EVA."""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Dict, List, Optional
import math
import re
import unicodedata


class TopicTracker:
    MAX_TOPICS = 20

    def __init__(self):
        self._topics: List[Dict] = []
        self._current_topic: Optional[str] = None
        self.logger = None

    def set_logger(self, logger):
        self.logger = logger

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().split())

    @staticmethod
    def _valid_topic(topic) -> Optional[str]:
        if not isinstance(topic, str):
            return None
        topic = " ".join(topic.split())
        return topic if topic else None

    @staticmethod
    def _importance(value) -> float:
        try:
            number = float(value)
            return max(0.0, min(1.0, number)) if math.isfinite(number) else 0.7
        except (TypeError, ValueError):
            return 0.7

    def add_topic(self, topic: str, importance: float = 0.7) -> None:
        topic = self._valid_topic(topic)
        if topic is None:
            if self.logger:
                self.logger.warning("[TopicTracker] Tópico vazio ou inválido ignorado")
            return

        key = self._normalize(topic)
        importance = self._importance(importance)
        now = datetime.now().isoformat()
        for index, existing in enumerate(self._topics):
            if self._normalize(existing["name"]) == key:
                existing["last_active"] = now
                existing["importance"] = max(self._importance(existing.get("importance")), importance)
                self._topics.pop(index)
                self._topics.insert(0, existing)
                self._current_topic = existing["name"]
                if self.logger:
                    self.logger.debug("[TopicTracker] Tópico retomado: %s", existing["name"])
                return

        entry = {
            "name": topic,
            "importance": importance,
            "first_mentioned": now,
            "last_active": now,
            "related_topics": [],
        }
        for existing in self._topics:
            if self._are_related(topic, existing["name"]):
                entry["related_topics"].append(existing["name"])
                related = existing.setdefault("related_topics", [])
                if topic not in related:
                    related.append(topic)

        self._topics.insert(0, entry)
        self._current_topic = topic
        self._topics = self._topics[:self.MAX_TOPICS]
        retained = {self._normalize(t["name"]) for t in self._topics}
        for existing in self._topics:
            existing["related_topics"] = [
                name for name in existing.get("related_topics", [])
                if self._normalize(name) in retained
            ]
        if self.logger:
            self.logger.debug("[TopicTracker] Novo tópico: %s", topic)

    def _are_related(self, topic1: str, topic2: str) -> bool:
        relations = {
            "arduino": {"iot", "automação", "hardware", "eletrônica"},
            "automação": {"casa", "segurança", "arduino", "iot"},
            "segurança": {"automação", "casa", "sistema", "sensor"},
            "eva": {"assistente", "voz", "conversa", "ia"},
            "casa": {"automação", "segurança", "projeto", "home"},
        }
        a, b = self._normalize(topic1), self._normalize(topic2)
        if not a or not b or a == b:
            return False
        if b in relations.get(a, set()) or a in relations.get(b, set()):
            return True
        # Similaridade somente por palavras inteiras, evitando "ia" dentro de "familia".
        words_a = set(re.findall(r"\w+", a))
        words_b = set(re.findall(r"\w+", b))
        return bool({word for word in words_a & words_b if len(word) >= 4})

    def get_current_topic(self) -> Optional[str]:
        return self._current_topic

    def get_recent_topics(self, limit: int = 5) -> List[str]:
        if not isinstance(limit, int) or limit <= 0:
            return []
        return [topic["name"] for topic in self._topics[:limit]]

    def get_topics(self, limit: int = 10) -> List[Dict]:
        if not isinstance(limit, int) or limit <= 0:
            return []
        ordered = sorted(
            self._topics,
            key=lambda item: (item.get("importance", 0.5), item.get("last_active", "")),
            reverse=True,
        )
        return deepcopy(ordered[:limit])

    def switch_topic(self, new_topic: str) -> None:
        topic = self._valid_topic(new_topic)
        if topic is None:
            return
        self.add_topic(topic)
        if self.logger:
            self.logger.debug("[TopicTracker] Tópico alterado para: %s", topic)

    def is_topic_active(self, topic: str, threshold_minutes: int = 10) -> bool:
        topic = self._valid_topic(topic)
        if topic is None:
            return False
        try:
            threshold = float(threshold_minutes)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(threshold) or threshold <= 0:
            return False
        for entry in self._topics:
            if self._normalize(entry["name"]) != self._normalize(topic):
                continue
            try:
                last_time = datetime.fromisoformat(entry["last_active"])
                now = datetime.now(last_time.tzinfo) if last_time.tzinfo else datetime.now()
                elapsed = (now - last_time).total_seconds()
                return 0 <= elapsed < threshold * 60
            except (ValueError, TypeError, KeyError):
                return False
        return False

    def clear(self) -> None:
        self._topics.clear()
        self._current_topic = None
        if self.logger:
            self.logger.debug("[TopicTracker] Tópicos limpos")

    def get_status(self) -> Dict:
        return {
            "current_topic": self._current_topic,
            "total_topics": len(self._topics),
            "recent_topics": self.get_recent_topics(5),
        }
