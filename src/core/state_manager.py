"""Gerenciador de estado global do Core."""

from enum import Enum, auto
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import asyncio


class SystemState(Enum):
    """Estados globais da EVA."""
    OFFLINE = auto()
    BOOTING = auto()
    IDLE = auto()
    LISTENING = auto()
    THINKING = auto()
    PLANNING = auto()
    EXECUTING = auto()
    LEARNING = auto()
    UPDATING = auto()
    ERROR = auto()
    SHUTDOWN = auto()


@dataclass
class StateTransition:
    """Registro de transição de estado."""
    from_state: SystemState
    to_state: SystemState
    timestamp: datetime = field(default_factory=datetime.now)
    reason: str = ""
    source: str = "system"
    data: Dict[str, Any] = field(default_factory=dict)


class StateManager:
    """
    Gerencia o estado global da EVA.
    A EVA inteira possui apenas UM estado global.
    Quando muda o estado, publica STATE_CHANGED.
    """
    
    def __init__(self, logger, event_bus):
        self.logger = logger
        self.event_bus = event_bus
        
        self._current_state = SystemState.OFFLINE
        self._previous_state: Optional[SystemState] = None
        self._transitions: List[StateTransition] = []
        self._max_history = 1000
        
        # Estados que são "ocupados"
        self._busy_states = {
            SystemState.THINKING,
            SystemState.PLANNING,
            SystemState.EXECUTING,
            SystemState.LEARNING,
            SystemState.UPDATING
        }
        
        # Estados que são "idle"
        self._idle_states = {
            SystemState.IDLE,
            SystemState.LISTENING
        }
    
    def set_state(self, new_state: SystemState, reason: str = "", 
                  source: str = "system", data: Dict[str, Any] = None) -> bool:
        """
        Define um novo estado.
        Retorna True se a transição foi válida.
        """
        # Verifica se é uma transição válida
        if not self._can_transition(new_state):
            self.logger.warning(f"Transição inválida: {self._current_state} -> {new_state}")
            return False
        
        # Executa transição
        self._previous_state = self._current_state
        self._current_state = new_state
        
        # Registra transição
        transition = StateTransition(
            from_state=self._previous_state,
            to_state=new_state,
            reason=reason,
            source=source,
            data=data or {}
        )
        self._transitions.append(transition)
        
        # Limita histórico
        if len(self._transitions) > self._max_history:
            self._transitions = self._transitions[-self._max_history:]
        
        self.logger.info(f"Estado alterado: {self._previous_state.name} -> {new_state.name} ({reason})")
        
        # Publica evento
        asyncio.create_task(self._publish_state_changed(transition))
        
        return True
    
    async def _publish_state_changed(self, transition: StateTransition) -> None:
        """Publica evento de mudança de estado."""
        await self.event_bus.publish_async(
            "STATE_CHANGED",
            {
                "previous": transition.from_state.name,
                "current": transition.to_state.name,
                "reason": transition.reason,
                "source": transition.source,
                "timestamp": transition.timestamp.isoformat(),
                "data": transition.data
            },
            source="state_manager"
        )
    
    def _can_transition(self, new_state: SystemState) -> bool:
        """Verifica se a transição é válida."""
        # Regras de transição
        valid = {
            SystemState.OFFLINE: [SystemState.BOOTING],
            SystemState.BOOTING: [SystemState.IDLE, SystemState.ERROR],
            SystemState.IDLE: [SystemState.LISTENING, SystemState.UPDATING, 
                              SystemState.SHUTDOWN, SystemState.ERROR],
            SystemState.LISTENING: [SystemState.THINKING, SystemState.IDLE, 
                                   SystemState.SHUTDOWN, SystemState.ERROR],
            SystemState.THINKING: [SystemState.PLANNING, SystemState.LISTENING,
                                  SystemState.ERROR, SystemState.IDLE],
            SystemState.PLANNING: [SystemState.EXECUTING, SystemState.THINKING,
                                  SystemState.ERROR, SystemState.IDLE],
            SystemState.EXECUTING: [SystemState.LEARNING, SystemState.LISTENING,
                                   SystemState.ERROR, SystemState.IDLE],
            SystemState.LEARNING: [SystemState.IDLE, SystemState.LISTENING,
                                  SystemState.ERROR],
            SystemState.UPDATING: [SystemState.IDLE, SystemState.ERROR],
            SystemState.ERROR: [SystemState.BOOTING, SystemState.SHUTDOWN],
            SystemState.SHUTDOWN: [SystemState.OFFLINE]
        }
        
        return new_state in valid.get(self._current_state, [])
    
    def get_state(self) -> SystemState:
        """Obtém o estado atual."""
        return self._current_state
    
    def get_previous_state(self) -> Optional[SystemState]:
        """Obtém o estado anterior."""
        return self._previous_state
    
    def get_state_name(self) -> str:
        """Obtém o nome do estado atual."""
        return self._current_state.name
    
    def get_history(self, limit: int = 50) -> List[StateTransition]:
        """Obtém histórico de transições."""
        return self._transitions[-limit:]
    
    def is_busy(self) -> bool:
        """Verifica se o sistema está ocupado."""
        return self._current_state in self._busy_states
    
    def is_idle(self) -> bool:
        """Verifica se o sistema está ocioso."""
        return self._current_state in self._idle_states
    
    def is_ready(self) -> bool:
        """Verifica se o sistema está pronto para interações."""
        return self._current_state in [SystemState.IDLE, SystemState.LISTENING]
    
    def can_accept_input(self) -> bool:
        """Verifica se o sistema pode aceitar entrada do usuário."""
        return self._current_state in [
            SystemState.IDLE,
            SystemState.LISTENING,
            SystemState.THINKING
        ]