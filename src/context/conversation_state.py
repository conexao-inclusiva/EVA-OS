# -*- coding: utf-8 -*-
"""Estado de uma conversa da EVA.

Mantém a interface original de ConversationState para os demais módulos.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ConversationState:
    user_id: str = "unknown"
    current_topic: Optional[str] = None
    recent_topics: List[str] = field(default_factory=list)
    active_entities: List[Dict[str, Any]] = field(default_factory=list)
    resolved_references: Dict[str, Any] = field(default_factory=dict)
    active_goal: Optional[str] = None
    recent_events: List[Dict[str, Any]] = field(default_factory=list)
    last_message: Optional[str] = None
    last_interaction: Optional[str] = None
    message_count: int = 0

    def __post_init__(self) -> None:
        if not self.last_interaction:
            self.last_interaction = datetime.now().isoformat()
        if not isinstance(self.resolved_references, dict):
            self.resolved_references = {}
        if not isinstance(self.active_entities, list):
            self.active_entities = []

    def update(self, message: str, entities: List[Dict] = None,
               topics: List[str] = None, references: Dict = None,
               goal: str = None) -> None:
        """Atualiza a conversa sem modificar os argumentos recebidos."""
        self.message_count += 1
        self.last_message = message
        self.last_interaction = datetime.now().isoformat()

        if isinstance(topics, list) and topics:
            new_topic = next((t for t in topics if isinstance(t, str) and t.strip()), None)
            if new_topic:
                if self.current_topic and self.current_topic != new_topic:
                    self.recent_topics = [t for t in self.recent_topics if t != self.current_topic]
                    self.recent_topics.append(self.current_topic)
                self.current_topic = new_topic
                self.recent_topics = self.recent_topics[-5:]

        if isinstance(entities, list):
            for entity in entities:
                if isinstance(entity, dict):
                    self._add_or_update_entity(entity)

        if isinstance(references, dict):
            self.resolved_references.update(references)
        elif isinstance(references, list):
            try:
                converted = dict(references)
                self.resolved_references.update(converted)
            except (ValueError, TypeError):
                pass

        if isinstance(goal, str) and goal.strip():
            self.active_goal = goal

    def _add_or_update_entity(self, entity: Dict) -> None:
        """Registra ou atualiza entidade sem alterar o dicionário de entrada."""
        name = entity.get("name")
        if not isinstance(name, str) or not name.strip():
            return
        name = name.strip()
        now = datetime.now().isoformat()
        aliases = entity.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []
        aliases = [a for a in aliases if isinstance(a, str) and a.strip()]

        for existing in self.active_entities:
            if not isinstance(existing, dict):
                continue
            if str(existing.get("name", "")).casefold() == name.casefold():
                count = existing.get("mention_count", 0)
                existing.update({k: v for k, v in entity.items()
                                 if k not in ("name", "aliases", "mention_count", "last_mentioned")})
                existing["mention_count"] = (count if isinstance(count, int) else 0) + 1
                existing["last_mentioned"] = now
                old_aliases = existing.get("aliases", [])
                if not isinstance(old_aliases, list):
                    old_aliases = []
                existing["aliases"] = list(dict.fromkeys(
                    a for a in old_aliases + aliases if isinstance(a, str)
                ))
                return

        new_entity = dict(entity)
        new_entity["name"] = name
        new_entity["aliases"] = aliases or [name]
        new_entity["mention_count"] = 1
        new_entity["last_mentioned"] = now
        self.active_entities.append(new_entity)
        self.active_entities = sorted(
            (e for e in self.active_entities if isinstance(e, dict)),
            key=lambda e: e.get("mention_count", 0) if isinstance(e.get("mention_count", 0), int) else 0,
            reverse=True,
        )[:10]

    def get_state(self) -> Dict[str, Any]:
        """Retorna uma cópia dos dados do estado, sem expor listas internas."""
        if not isinstance(self.resolved_references, dict):
            self.resolved_references = {}
        return {
            "user_id": self.user_id,
            "current_topic": self.current_topic,
            "recent_topics": list(self.recent_topics),
            "active_entities": [dict(e) for e in self.active_entities if isinstance(e, dict)],
            "resolved_references": dict(self.resolved_references),
            "active_goal": self.active_goal,
            "message_count": self.message_count,
            "last_message": self.last_message,
            "last_interaction": self.last_interaction,
        }

    def get_entity(self, name: str) -> Optional[Dict]:
        """Busca entidade por nome ou alias, ignorando maiúsculas/minúsculas."""
        if not isinstance(name, str):
            return None
        target = name.casefold()
        for entity in self.active_entities:
            if not isinstance(entity, dict):
                continue
            if str(entity.get("name", "")).casefold() == target:
                return dict(entity)
            aliases = entity.get("aliases", [])
            if isinstance(aliases, list) and any(
                isinstance(alias, str) and alias.casefold() == target for alias in aliases
            ):
                return dict(entity)
        return None

    def clear(self) -> None:
        """Reinicia todos os dados de uma conversa, mantendo o identificador."""
        self.current_topic = None
        self.recent_topics = []
        self.active_entities = []
        self.resolved_references = {}
        self.active_goal = None
        self.recent_events = []
        self.last_message = None
        self.last_interaction = datetime.now().isoformat()
        self.message_count = 0
