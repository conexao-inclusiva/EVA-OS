"""Orquestrador de estados do sistema."""

from typing import Dict, Any, Optional
from datetime import datetime

from src.core.state_manager import SystemState


class StateOrchestrator:
    """
    Orquestra os estados do sistema.
    """
    
    def __init__(self, consciousness_manager):
        self.consciousness = consciousness_manager
        self.logger = consciousness_manager.logger
        self.state_manager = consciousness_manager.context_manager.system._data
    
    async def transition_to(self, new_state: SystemState, reason: str = "",
                            data: Dict[str, Any] = None) -> bool:
        """
        Transiciona para um novo estado.
        """
        # Valida transição
        if not self._can_transition(new_state):
            self.logger.warning(f"Transição inválida: {self._get_current_state()} -> {new_state}")
            return False
        
        # Executa transição
        old_state = self._get_current_state()
        
        # Notifica sistema
        await self.consciousness.event_bus.publish_async(
            "system.state.pre_transition",
            {
                "from": old_state,
                "to": new_state,
                "reason": reason,
                "data": data
            },
            source="consciousness"
        )
        
        # Muda estado
        self.state_manager["state"] = new_state.value
        self.state_manager["last_transition"] = datetime.now().isoformat()
        
        self.logger.info(f"Estado alterado: {old_state} -> {new_state} ({reason})")
        
        # Notifica sistema
        await self.consciousness.event_bus.publish_async(
            "system.state.transitioned",
            {
                "from": old_state,
                "to": new_state,
                "reason": reason,
                "data": data,
                "timestamp": datetime.now().isoformat()
            },
            source="consciousness"
        )
        
        return True
    
    def _can_transition(self, new_state: SystemState) -> bool:
        """Verifica se a transição é válida."""
        current = self._get_current_state()
        
        # Regras de transição
        valid = {
            "IDLE": ["LISTENING", "THINKING", "UPDATING", "MAINTENANCE"],
            "LISTENING": ["THINKING", "IDLE"],
            "THINKING": ["PLANNING", "LISTENING"],
            "PLANNING": ["EXECUTING", "THINKING"],
            "EXECUTING": ["LEARNING", "LISTENING"],
            "LEARNING": ["IDLE", "LISTENING"],
            "UPDATING": ["IDLE"],
            "MAINTENANCE": ["IDLE"],
            "ERROR": ["RECOVERING"],
            "RECOVERING": ["IDLE"]
        }
        
        current_name = current if isinstance(current, str) else current.value
        new_name = new_state.value
        
        return new_name in valid.get(current_name, [])
    
    def _get_current_state(self) -> str:
        """Obtém o estado atual."""
        return self.state_manager.get("state", "IDLE")
    
    async def handle_error(self, error: str, source: str = "system") -> None:
        """
        Manipula um erro, transicionando para ERROR se necessário.
        """
        current = self._get_current_state()
        
        if current != "ERROR":
            await self.transition_to(
                SystemState.ERROR,
                reason=f"Erro de {source}: {error[:100]}",
                data={"error": error, "source": source}
            )
    
    async def recover(self) -> bool:
        """
        Tenta se recuperar de um estado de erro.
        """
        current = self._get_current_state()
        
        if current != "ERROR":
            return False
        
        await self.transition_to(
            SystemState.RECOVERING,
            reason="Iniciando recuperação"
        )
        
        # TODO: Executar recuperação
        
        await self.transition_to(
            SystemState.IDLE,
            reason="Recuperação concluída"
        )
        
        return True