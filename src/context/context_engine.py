# -*- coding: utf-8 -*-
"""ContextEngine - Orquestrador central de contexto e memória da EVA."""

import re
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.context.conversation_state import ConversationState
from src.context.entity_tracker import EntityTracker
from src.context.topic_tracker import TopicTracker
from src.context.reference_resolver import ReferenceResolver


class ContextEngine:
    """Organiza estado, entidades, tópicos, referências e memórias."""

    def __init__(self, event_bus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self._running = False

        self.state = ConversationState()
        self.entity_tracker = EntityTracker()
        self.topic_tracker = TopicTracker()

        # Componentes contextuais independentes por usuario.
        self._user_contexts = {}
        import asyncio
        self._process_lock = asyncio.Lock()
        self.reference_resolver = ReferenceResolver()

        self.entity_tracker.set_logger(logger)
        self.topic_tracker.set_logger(logger)
        self.reference_resolver.set_logger(logger)

        # Histórico curto para resolução de referências, separado por usuário.
        self._recent_messages = defaultdict(lambda: deque(maxlen=12))
        self._current_user_id = None
        self.logger.info("🧠 [ContextEngine] Inicializado")

    async def initialize(self) -> None:
        self.logger.info("🧠 [ContextEngine] Inicializando...")
        await self._load_state()
        self._running = True
        self.logger.info("🧠 [ContextEngine] Inicializado")

    async def process(self, message: str, user_id: str,
                      memories: Optional[List[Dict]] = None) -> Dict[str, Any]:
        async with self._process_lock:
            if not isinstance(message, str):
                message = str(message) if message is not None else ""
            user_id = str(user_id or "unknown")
            self._current_user_id = user_id

            # Seleciona componentes exclusivos deste usuario.
            if user_id not in self._user_contexts:
                state = ConversationState(user_id=user_id)
                entities = EntityTracker()
                topics = TopicTracker()
                entities.set_logger(self.logger)
                topics.set_logger(self.logger)
                self._user_contexts[user_id] = (
                    state, entities, topics
                )

            (
                self.state,
                self.entity_tracker,
                self.topic_tracker,
            ) = self._user_contexts[user_id]

            self.logger.debug("🧠 [ContextEngine] Processando mensagem de %s", user_id)

            self.state.update(message)
            self.state.user_id = user_id

            entities = self._extract_entities(message)
            for entity in entities:
                self.entity_tracker.add_entity(
                    name=entity["name"],
                    entity_type=entity["type"],
                    aliases=entity.get("aliases", []),
                    metadata=entity.get("metadata", {}),
                )

            topics = self._detect_topics(message)
            for topic in topics:
                self.topic_tracker.add_topic(topic)

            # O texto atual só entra no histórico DEPOIS da resolução.
            recent_messages = self._get_recent_messages(user_id)
            active_entities = self.entity_tracker.get_active_entities(5)
            recent_topics = self.topic_tracker.get_recent_topics(3)
            references = self.reference_resolver.resolve(
                text=message,
                entities=active_entities,
                topics=recent_topics,
                recent_messages=recent_messages,
                context={"last_entity": self._get_last_entity()},
            )
            if not isinstance(references, dict):
                self.logger.warning("[ContextEngine] Resolver retornou %s; ignorando referências inválidas", type(references).__name__)
                references = {}

            if isinstance(memories, dict):
                # Aceita saída do MemoryManager além da lista direta de memórias.
                memories = memories.get("relevant_memories") or memories.get("history") or []
            if not isinstance(memories, list):
                memories = []
            relevant_memories = self._rank_memories(message, entities, topics, memories)

            context = self._build_context(
                message=message,
                user_id=user_id,
                entities=entities,
                topics=topics,
                references=references,
                memories=relevant_memories,
                state=self.state.get_state(),
            )
            self._recent_messages[user_id].append(message)
            self._save_context(context)
            return context

    def _extract_entities(self, text: str) -> List[Dict]:
        patterns = [
            (r"\b[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+)*\b", "proper_name"),
            (r"\b(?:Arduino|Raspberry|ESP32|Jellyfin|MikroTik|Windows|Linux|Ubuntu)\b", "tech"),
            (r"\b(?:projeto|sistema|servidor|computador|pc|hd|ssd|sensor|lâmpada)\b", "object"),
        ]
        entities = []
        seen = set()
        for pattern, entity_type in patterns:
            flags = re.IGNORECASE if entity_type != "proper_name" else 0
            for match in re.finditer(pattern, text, flags):
                name = match.group(0).strip()
                key = (name.casefold(), entity_type)
                ignored_names = {
                    "meu", "minha", "meus", "minhas",
                    "qual", "quais", "quem", "como",
                    "quando", "onde", "porque", "porqu?",
                    "o", "a", "os", "as",
                    "ele", "ela", "eles", "elas",
                    "dele", "dela", "deles", "delas",
                    "esse", "essa", "este", "esta",
                    "isso", "isto", "aquilo",
                    "eu", "voce", "voc?", "nos", "n?s",
                }
                if (
                    len(name) > 2
                    and key not in seen
                    and not (
                        entity_type == "proper_name"
                        and name.casefold() in ignored_names
                    )
                ):
                    seen.add(key)
                    entities.append({"name": name, "type": entity_type, "aliases": [name.lower()]})
        return entities

    def _detect_topics(self, text: str) -> List[str]:
        topic_keywords = {
            "arduino": ["arduino", "nano", "uno", "microcontrolador"],
            "automação": ["automação", "casa inteligente", "iot", "smart home"],
            "segurança": ["segurança", "alarme", "sensor", "câmera"],
            "servidor": ["servidor", "pc", "computador", "nas"],
            "projeto": ["projeto", "desenvolvimento", "criação"],
            "eva": ["eva", "assistente", "voz"],
            "programação": ["programar", "código", "python", "javascript"],
        }
        lower = text.casefold()
        topics = [topic for topic, words in topic_keywords.items()
                  if any(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", lower)
                         for word in words)]
        if not topics:
            for word in re.findall(r"\w+", lower):
                if len(word) > 4 and word not in {"porque", "quando", "onde", "como", "então"}:
                    topics.append(word)
                    break
        return topics[:3]

    def _rank_memories(self, message: str, entities: List[Dict],
                       topics: List[str], memories: List[Dict]) -> List[Dict]:
        scored = []
        now = datetime.now(timezone.utc)
        for memory in memories:
            if not isinstance(memory, dict):
                continue
            content = str(memory.get("content") or "").casefold()
            score = 0.0
            for entity in entities:
                name = str(entity.get("name") or "").casefold()
                if name and name in content:
                    score += 0.3
            for topic in topics:
                if topic and topic.casefold() in content:
                    score += 0.2
            timestamp = memory.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    mem_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    if mem_time.tzinfo is None:
                        mem_time = mem_time.astimezone()
                    age = (now - mem_time.astimezone(timezone.utc)).total_seconds()
                    if 0 <= age < 600:
                        score += 0.3
                    elif 0 <= age < 3600:
                        score += 0.1
                except (ValueError, TypeError, OverflowError):
                    pass
            try:
                importance = max(0.0, min(1.0, float(memory.get("importance", 0.5))))
            except (ValueError, TypeError):
                importance = 0.5
            score += importance * 0.2
            scored.append((score, memory))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [memory for _, memory in scored[:5]]

    def _build_context(self, message: str, user_id: str, entities: List[Dict],
                       topics: List[str], references: Dict, memories: List[Dict],
                       state: Dict) -> Dict[str, Any]:
        if not isinstance(state, dict):
            self.logger.warning("[ContextEngine] Estado inválido (%s)", type(state).__name__)
            state = {}
        else:
            state = dict(state)
        resolved = state.get("resolved_references")
        if resolved is not None and not isinstance(resolved, dict):
            if isinstance(resolved, list):
                try:
                    resolved = dict(resolved)
                except (ValueError, TypeError):
                    resolved = {}
            else:
                resolved = {}
            state["resolved_references"] = resolved

        return {
            "message": message,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "current_topic": self.topic_tracker.get_current_topic(),
            # Mantém lista: é o formato original produzido pelo extrator.
            "entities": entities,
            "topics": topics,
            "references": references.get("references", {}),
            "unresolved_references": references.get("unresolved", []),
            "memories": memories,
            "state": state,
            "entity_status": self.entity_tracker.get_status(),
            "topic_status": self.topic_tracker.get_status(),
        }

    def _get_recent_messages(self, user_id: Optional[str] = None) -> List[str]:
        user_id = str(user_id or self._current_user_id or "unknown")
        return list(self._recent_messages.get(user_id, ()))

    def _get_last_entity(self) -> Optional[Dict]:
        entities = self.entity_tracker.get_active_entities(1)
        return entities[0] if entities else None

    def _save_context(self, context: Dict) -> None:
        """Ponto de extensão: persistência depende do módulo WorkingMemory."""
        return None

    async def _load_state(self) -> None:
        """Ponto de extensão: estado persistente depende de integração futura."""
        return None

    async def get_state(self) -> Dict:
        return {
            "conversation": self.state.get_state(),
            "entities": self.entity_tracker.get_status(),
            "topics": self.topic_tracker.get_status(),
        }

    async def shutdown(self) -> None:
        self.logger.info("🧠 [ContextEngine] Desligando...")
        self._running = False
        self.logger.info("🧠 [ContextEngine] Desligado")
