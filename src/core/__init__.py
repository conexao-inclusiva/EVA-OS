"""Core - Espinha dorsal da EVA OS."""

from src.core.event_bus import EventBus, Event, EventPriority
from src.core.service_registry import ServiceRegistry, Service, ServiceStatus
from src.core.dependency_container import DependencyContainer
from src.core.lifecycle_manager import LifecycleManager, ModuleState, ModuleInfo
from src.core.module_loader import ModuleLoader
from src.core.state_manager import StateManager, SystemState, StateTransition
from src.core.health_manager import HealthManager
from src.core.plugin_manager import PluginManager, Plugin, PluginManifest, PluginStatus, PluginType

# 🔥 ADICIONADO: Import do LLM Decision Gate
from src.core.llm_decision_gate import LLMDecisionGate


class Core:
    """
    Core da EVA OS.
    Fornece toda a infraestrutura base.
    """
    
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        
        # 1. EventBus (primeiro, pois tudo depende dele)
        self.event_bus = EventBus(logger)
        
        # 2. ServiceRegistry
        self.service_registry = ServiceRegistry(logger)
        
        # 3. DependencyContainer
        self.container = DependencyContainer(logger, self.service_registry)
        
        # 4. StateManager
        self.state_manager = StateManager(logger, self.event_bus)
        
        # 5. LifecycleManager
        self.lifecycle_manager = LifecycleManager(logger, self.event_bus, self.service_registry)
        
        # 6. PluginManager (substitui ModuleLoader)
        self.plugin_manager = PluginManager(logger, self.event_bus, config, self.service_registry)
        
        # 7. HealthManager
        self.health_manager = HealthManager(logger, self.event_bus, config)
        
        # Registra serviços core
        self._register_core_services()
    
    def _register_core_services(self) -> None:
        """Registra serviços do Core."""
        self.service_registry.register("event_bus", self.event_bus)
        self.service_registry.register("service_registry", self.service_registry)
        self.service_registry.register("container", self.container)
        self.service_registry.register("state_manager", self.state_manager)
        self.service_registry.register("lifecycle_manager", self.lifecycle_manager)
        self.service_registry.register("plugin_manager", self.plugin_manager)
        self.service_registry.register("health_manager", self.health_manager)
    
    async def initialize(self) -> None:
        """Inicializa o Core."""
        self.logger.info("Inicializando Core...")
        
        # 1. EventBus
        await self.event_bus.initialize()
        
        # 2. HealthManager
        await self.health_manager.initialize()
        
        # 3. StateManager
        self.state_manager.set_state(SystemState.BOOTING, "Core inicializando", "core")
        
        self.logger.info("Core inicializado")
    
    async def start(self) -> None:
        """Inicia o Core."""
        self.logger.info("Iniciando Core...")
        
        # Muda para IDLE
        self.state_manager.set_state(SystemState.IDLE, "Core pronto", "core")
        
        self.logger.info("Core pronto")
    
    async def shutdown(self) -> None:
        """Desliga o Core."""
        self.logger.info("Desligando Core...")
        
        # Muda para SHUTDOWN
        self.state_manager.set_state(SystemState.SHUTDOWN, "Core desligando", "core")
        
        # Desliga componentes (ordem reversa)
        await self.plugin_manager.shutdown()
        await self.health_manager.shutdown()
        await self.event_bus.shutdown()
        
        self.logger.info("Core desligado")


__all__ = [
    # Classes base
    "Core",
    "EventBus",
    "Event",
    "EventPriority",
    "ServiceRegistry",
    "Service",
    "ServiceStatus",
    "DependencyContainer",
    "LifecycleManager",
    "ModuleState",
    "ModuleInfo",
    "StateManager",
    "SystemState",
    "StateTransition",
    "HealthManager",
    # Plugin Manager
    "PluginManager",
    "Plugin",
    "PluginManifest",
    "PluginStatus",
    "PluginType",
    # 🔥 ADICIONADO
    "LLMDecisionGate"
]