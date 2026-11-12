"""Contexto da conversa atual."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class Message:
    """Uma mensagem na conversa."""
    sender: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationContext:
    """
    Contexto da conversa atual.
    
    Mantém:
    - Histórico recente
    - Assunto atual
    - Intenção detectada
    - Referências ("isso", "ele", "aquele")
    - Tópicos anteriores
    """
    
    def __init__(self, max_history: int = 50):
        self.max_history = max_history
        self._messages: List[Message] = []
        self._data: Dict[str, Any] = {
            "current_topic": None,
            "previous_topics": [],
            "detected_intent": None,
            "entities": {},
            "referents": {},  # "isso" -> "o que foi mencionado"
            "last_update": None
        }
    
    def add_message(self, sender: str, content: str, metadata: Dict[str, Any] = None) -> None:
        """Adiciona uma mensagem ao histórico."""
        message = Message(
            sender=sender,
            content=content,
            metadata=metadata or {}
        )
        self._messages.append(message)
        
        # Limita histórico
        if len(self._messages) > self.max_history:
            self._messages = self._messages[-self.max_history:]
        
        # Atualiza metadados
        self._data["last_update"] = datetime.now()
        
        # Detecta tópico (simples)
        self._detect_topic(content)
    
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtém histórico recente."""
        messages = self._messages[-limit:] if limit > 0 else self._messages
        return [
            {
                "sender": m.sender,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
                "metadata": m.metadata
            }
            for m in messages
        ]
    
    def get_last_n_messages(self, n: int = 5) -> List[Message]:
        """Obtém as últimas N mensagens."""
        return self._messages[-n:] if n > 0 else self._messages
    
    def get_conversation_chain(self, n: int = 10) -> str:
        """Gera a cadeia de conversação."""
        messages = self._messages[-n:] if n > 0 else self._messages
        chain = []
        for msg in messages:
            chain.append(f"[{msg.sender}] {msg.content}")
        return "\n".join(chain)
    
    def get_current_topic(self) -> Optional[str]:
        """Obtém o tópico atual."""
        return self._data.get("current_topic")
    
    def get_detected_intent(self) -> Optional[str]:
        """Obtém a intenção detectada."""
        return self._data.get("detected_intent")
    
    def set_intent(self, intent: str) -> None:
        """Define a intenção detectada."""
        self._data["detected_intent"] = intent
    
    def set_topic(self, topic: str) -> None:
        """Define o tópico atual."""
        if topic and topic != self._data["current_topic"]:
            if self._data["current_topic"]:
                self._data["previous_topics"].append(self._data["current_topic"])
            self._data["current_topic"] = topic
    
    def resolve_referent(self, word: str) -> Optional[str]:
        """Resolve uma referência (ex: "isso" -> "o que foi mencionado")."""
        return self._data.get("referents", {}).get(word.lower())
    
    def _detect_topic(self, content: str) -> None:
        """Detecta tópico a partir do conteúdo (simples)."""
        # TODO: Implementar detecção de tópico com IA
        # Por enquanto, usa regras simples
        content_lower = content.lower()
        
        topics = {
            "luz": "Controle de luz",
            "temperatura": "Controle de temperatura",
            "música": "Música e entretenimento",
            "lembrete": "Lembretes",
            "programar": "Programação",
            "estudar": "Estudo",
            "compras": "Lista de compras"
        }
        
        for keyword, topic in topics.items():
            if keyword in content_lower:
                self.set_topic(topic)
                break
    
    def set(self, key: str, value: Any) -> None:
        """Define um valor no contexto."""
        self._data[key] = value
        self._data["last_update"] = datetime.now()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obtém um valor do contexto."""
        return self._data.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """Obtém todo o contexto."""
        result = self._data.copy()
        result["history"] = self.get_history(10)
        result["message_count"] = len(self._messages)
        return result
    
    def clear(self) -> None:
        """Limpa o contexto."""
        self._messages.clear()
        self._data = {
            "current_topic": None,
            "previous_topics": [],
            "detected_intent": None,
            "entities": {},
            "referents": {},
            "last_update": datetime.now()
        }