"""Gerenciamento de contexto da Consciência."""

from typing import Any, Dict, Optional
from datetime import datetime


class ContextManager:
    """Gerencia o contexto atual da conversa e interações."""
    
    def __init__(self):
        self._context: Dict[str, Any] = {
            "current_topic": None,
            "last_interaction": None,
            "participants": [],
            "conversation_history": [],
            "active_goals": [],
            "temporary_state": {}
        }
    
    def set(self, key: str, value: Any) -> None:
        """Define um valor no contexto."""
        self._context[key] = value
        self._context["last_update"] = datetime.now()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obtém um valor do contexto."""
        return self._context.get(key, default)
    
    def update_topic(self, topic: str) -> None:
        """Atualiza o tópico atual da conversa."""
        self._context["current_topic"] = topic
        self._context["topic_history"] = self._context.get("topic_history", [])
        self._context["topic_history"].append({
            "topic": topic,
            "timestamp": datetime.now()
        })
    
    def add_participant(self, participant: str) -> None:
        """Adiciona um participante à conversa."""
        if participant not in self._context["participants"]:
            self._context["participants"].append(participant)
    
    def clear_temporary(self) -> None:
        """Limpa o estado temporário."""
        self._context["temporary_state"] = {}
    
    def get_context_string(self) -> str:
        """Gera uma string de contexto para IA."""
        # TODO: Gerar contexto formatado para LLM
        return f"Tópico atual: {self._context['current_topic']}"