# -*- coding: utf-8 -*-

"""
ConversationFlow - Gerencia o fluxo da conversa.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

from src.core.event_types import EventType
from src.kernel.events import Event, EventBus


class ConversationFlow:
    """
    Gerencia o fluxo da conversa.
    """
    
    def __init__(self, event_bus: EventBus, logger, config):  # ✅ CORRIGIDO: 3 argumentos
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self._running = False
        
        # Histórico do fluxo
        self._flow_history: List[Dict] = []
        self._current_flow = None
        
        self.logger.info("🌊 [ConversationFlow] Inicializado")
    
    async def initialize(self) -> None:
        """Inicializa o ConversationFlow."""
        self.logger.info("🌊 [ConversationFlow] Inicializando...")
        self._running = True
        self.logger.info("🌊 [ConversationFlow] Inicializado")
    
    async def process(self, context: Dict) -> Dict:
        """
        Processa o fluxo da conversa.
        
        Args:
            context: Contexto da conversa
            
        Returns:
            Dicionário com informações do fluxo
        """
        self.logger.debug("🌊 [ConversationFlow] Processando...")
        
        message = context.get("message", "")
        user_id = context.get("user_id", "unknown")
        
        # Registra no histórico
        entry = {
            "user_id": user_id,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "flow_id": len(self._flow_history) + 1
        }
        self._flow_history.append(entry)
        
        # Mantém apenas as últimas 50 interações
        if len(self._flow_history) > 50:
            self._flow_history = self._flow_history[-50:]
        
        # Determina o fluxo atual
        flow_info = {
            "current_flow": self._current_flow,
            "total_interactions": len(self._flow_history),
            "recent_messages": self._flow_history[-5:] if self._flow_history else []
        }
        
        self._current_flow = flow_info
        
        return flow_info
    
    async def get_history(self, limit: int = 10) -> List[Dict]:
        """Retorna o histórico recente."""
        return self._flow_history[-limit:] if self._flow_history else []
    
    async def shutdown(self) -> None:
        """Desliga o ConversationFlow."""
        self.logger.info("🌊 [ConversationFlow] Desligando...")
        self._running = False
        self.logger.info("🌊 [ConversationFlow] Desligado")