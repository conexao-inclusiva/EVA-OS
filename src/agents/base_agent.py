"""Classe base para todos os agentes da EVA."""

from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from datetime import datetime

from src.kernel.events import Event, EventBus


class BaseAgent(ABC):
    """
    Classe base para todos os agentes.
    
    Todo agente deve herdar desta classe e implementar:
    - initialize(): Inicialização
    - start(): Início das operações
    - process(): Processamento de tarefas
    - shutdown(): Desligamento
    - health_check(): Verificação de saúde
    """
    
    # Atributos de plugin (devem ser sobrescritos)
    __plugin_name__ = "base_agent"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Agente base da EVA"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["agent", "base"]
    __plugin_capabilities__ = ["base"]
    __plugin_requires__ = ["event_bus", "logger"]
    
    def __init__(self, event_bus: EventBus, logger, config, name: str = None):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        # Nome do agente
        self.name = name or self.__class__.__name__.lower().replace("agent", "")
        
        # Estado
        self._running = False
        self._initialized = False
        self._task_count = 0
        self._error_count = 0
        self._last_task: Optional[Dict[str, Any]] = None
        self._started_at: Optional[datetime] = None
        
        # Capacidades
        self.capabilities = self._get_capabilities()
    
    @abstractmethod
    async def initialize(self) -> None:
        """Inicializa o agente."""
        self._initialized = True
        self.logger.info(f"Agente {self.name} inicializado")
    
    @abstractmethod
    async def start(self) -> None:
        """Inicia o agente."""
        self._running = True
        self._started_at = datetime.now()
        self.logger.info(f"Agente {self.name} iniciado")
    
    @abstractmethod
    async def process(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa uma tarefa.
        
        Args:
            task: Dicionário com a tarefa a ser processada
            
        Returns:
            Dict com o resultado do processamento
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Desliga o agente."""
        self._running = False
        self.logger.info(f"Agente {self.name} desligado")
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Verifica a saúde do agente."""
        return {
            "name": self.name,
            "running": self._running,
            "initialized": self._initialized,
            "task_count": self._task_count,
            "error_count": self._error_count,
            "uptime": (datetime.now() - self._started_at).total_seconds() if self._started_at else 0
        }
    
    def _get_capabilities(self) -> List[str]:
        """Obtém as capacidades do agente."""
        return getattr(self, "__plugin_capabilities__", ["general"])
    
    def can_handle(self, intent: str) -> bool:
        """Verifica se o agente pode lidar com uma intenção."""
        # Por padrão, verifica se a intenção está nas capacidades
        return intent in self.capabilities or "general" in self.capabilities
    
    async def handle_event(self, event: Event) -> None:
        """Manipula um evento recebido."""
        if not self._running:
            self.logger.warning(f"Agente {self.name} recebeu evento mas está desligado")
            return
        
        try:
            # Extrai tarefa do evento
            task = event.payload.get("task", {})
            if not task:
                task = event.payload
            
            # Processa a tarefa
            result = await self.process(task)
            
            # Registra
            self._task_count += 1
            self._last_task = {
                "task": task,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
            
            # Publica resultado
            await self.event_bus.publish_async(
                "agent.task_completed",
                {
                    "agent": self.name,
                    "result": result,
                    "original_event": event.id if hasattr(event, 'id') else None,
                    "timestamp": datetime.now().isoformat()
                },
                source=self.name
            )
            
        except Exception as e:
            self._error_count += 1
            self.logger.error(f"Erro no agente {self.name}: {e}")
            
            # Publica erro
            await self.event_bus.publish_async(
                "agent.task_failed",
                {
                    "agent": self.name,
                    "error": str(e),
                    "task": event.payload,
                    "timestamp": datetime.now().isoformat()
                },
                source=self.name
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas do agente."""
        return {
            "name": self.name,
            "running": self._running,
            "initialized": self._initialized,
            "task_count": self._task_count,
            "error_count": self._error_count,
            "uptime": (datetime.now() - self._started_at).total_seconds() if self._started_at else 0,
            "capabilities": self.capabilities,
            "last_task": self._last_task
        }