"""Loop de feedback."""

from typing import Dict, Any


class FeedbackLoop:
    """Processa feedback do usuário."""
    
    def __init__(self, learning_manager):
        self.learning_manager = learning_manager
        self.logger = learning_manager.logger
        self._feedback_history = []
    
    async def process(self, feedback_type: str, content: Dict[str, Any]) -> None:
        """Processa feedback."""
        self._feedback_history.append({
            "type": feedback_type,
            "content": content,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        })
        self.logger.info(f"Feedback recebido: {feedback_type}")
    
    async def process_agent_response(self, agent: str, response: Dict[str, Any]) -> None:
        """Processa resposta de agente."""
        if response.get("success") == False:
            self.logger.warning(f"Agente {agent} falhou: {response.get('error')}")