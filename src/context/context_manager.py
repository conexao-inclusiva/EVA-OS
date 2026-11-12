# -*- coding: utf-8 -*-
"""ContextManager: fornece contexto básico como fallback do ContextEngine.

Não duplica o rastreamento de entidades, tópicos ou referências realizado
pelo ContextEngine. Um ConversationState pode ser associado explicitamente.
"""

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional


class ContextManager:
    """Gerencia um contexto básico de conversa, mantendo a API existente."""

    def __init__(self, event_bus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self._running = False
        self._conversation_state = None
        self.logger.info("📋 [ContextManager] Inicializado")

    async def initialize(self) -> None:
        self.logger.info("📋 [ContextManager] Inicializando...")
        self._running = True
        self.logger.info("📋 [ContextManager] Inicializado")

    async def process(self, text: str, user_id: str) -> Dict[str, Any]:
        """Retorna contexto básico; não substitui o ContextEngine."""
        if not isinstance(text, str):
            raise TypeError("text deve ser uma string")
        if not isinstance(user_id, str):
            raise TypeError("user_id deve ser uma string")

        self.logger.debug("📋 [ContextManager] Processando: %r", text[:50])
        context: Dict[str, Any] = {
            "message": text,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "entities": [],
            "topics": [],
            "references": {},
        }

        if self._conversation_state is not None:
            try:
                state = self._conversation_state.get_state()
                if isinstance(state, dict):
                    context["state"] = deepcopy(state)
                else:
                    self.logger.warning(
                        "📋 [ContextManager] get_state retornou %s; estado ignorado",
                        type(state).__name__,
                    )
            except Exception:
                self.logger.exception("📋 [ContextManager] Falha ao consultar estado da conversa")

        return context

    async def set_conversation_state(self, state) -> None:
        """Associa um objeto de estado com método get_state(), ou None."""
        if state is not None and not callable(getattr(state, "get_state", None)):
            raise TypeError("state deve implementar get_state() ou ser None")
        self._conversation_state = state
        self.logger.debug("📋 [ContextManager] Estado da conversa definido")

    async def get_conversation_state(self):
        """Retorna o objeto de estado associado (API original)."""
        return self._conversation_state

    async def shutdown(self) -> None:
        self.logger.info("📋 [ContextManager] Desligando...")
        self._running = False
        self.logger.info("📋 [ContextManager] Desligado")
