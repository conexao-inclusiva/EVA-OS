"""Gerenciador de ciclo de vida do Core."""

from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import asyncio


class ModuleState(Enum):
    """Estados de um módulo no ciclo de vida."""
    CREATED = auto()
    INITIALIZED = auto()
    STARTING = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    FAILED = auto()


class ModuleInfo:
    """Informações de um módulo."""
    
    def __init__(self, name: str, module: Any, dependencies: List[str] = None):
        self.name = name
        self.module = module
        self.dependencies = dependencies or []
        self.state = ModuleState.CREATED
        
        self.created_at = datetime.now()
        self.initialized_at: Optional[datetime] = None
        self.started_at: Optional[datetime] = None
        self.stopped_at: Optional[datetime] = None
        
        self.error: Optional[str] = None
        self.retry_count = 0
        self.max_retries = 3


class LifecycleManager:
    """
    Gerencia a vida dos módulos.
    Estados: CREATED -> INITIALIZED -> STARTING -> RUNNING -> STOPPING -> STOPPED
    """
    
    def __init__(self, logger, event_bus, service_registry):
        self.logger = logger
        self.event_bus = event_bus
        self.registry = service_registry
        
        self._modules: Dict[str, ModuleInfo] = {}
        self._startup_order: List[str] = []
        
        # Configurações
        self._timeout = 30  # segundos
        self._max_retries = 3
    
    def register(self, name: str, module: Any, dependencies: List[str] = None) -> None:
        """Registra um módulo no ciclo de vida."""
        if name in self._modules:
            self.logger.warning(f"Módulo {name} já registrado")
            return
        
        info = ModuleInfo(name, module, dependencies)
        self._modules[name] = info
        self.logger.info(f"Módulo registrado: {name}")
        
        # Ordena topologicamente
        self._update_startup_order()
    
    def _update_startup_order(self) -> None:
        """Atualiza ordem de inicialização (topológica)."""
        # Ordena por número de dependências (mais dependências primeiro)
        self._startup_order = sorted(
            self._modules.keys(),
            key=lambda x: len(self._modules[x].dependencies),
            reverse=True
        )
    
    async def initialize_all(self) -> None:
        """Inicializa todos os módulos."""
        self.logger.info("Inicializando todos os módulos...")
        
        for name in self._startup_order:
            info = self._modules[name]
            if info.state == ModuleState.CREATED:
                await self._initialize_module(name)
    
    async def start_all(self) -> None:
        """Inicia todos os módulos."""
        self.logger.info("Iniciando todos os módulos...")
        
        # Inicializa primeiro
        for name in self._startup_order:
            info = self._modules[name]
            if info.state == ModuleState.CREATED:
                await self._initialize_module(name)
        
        # Depois inicia
        for name in self._startup_order:
            info = self._modules[name]
            if info.state == ModuleState.INITIALIZED:
                await self._start_module(name)
    
    async def _initialize_module(self, name: str) -> bool:
        """Inicializa um módulo específico."""
        info = self._modules[name]
        
        try:
            self.logger.debug(f"Inicializando módulo: {name}")
            
            module = info.module
            if hasattr(module, "initialize"):
                if asyncio.iscoroutinefunction(module.initialize):
                    await module.initialize()
                else:
                    module.initialize()
            
            info.state = ModuleState.INITIALIZED
            info.initialized_at = datetime.now()
            info.error = None
            
            self.logger.info(f"Módulo inicializado: {name}")
            return True
            
        except Exception as e:
            info.state = ModuleState.FAILED
            info.error = str(e)
            self.logger.error(f"Erro ao inicializar {name}: {e}")
            return False
    
    async def _start_module(self, name: str) -> bool:
        """Inicia um módulo específico."""
        info = self._modules[name]
        
        # Verifica dependências
        if not self._check_dependencies(name):
            self.logger.error(f"Dependências não satisfeitas para {name}")
            info.state = ModuleState.FAILED
            return False
        
        try:
            self.logger.debug(f"Iniciando módulo: {name}")
            
            module = info.module
            if hasattr(module, "start"):
                if asyncio.iscoroutinefunction(module.start):
                    await module.start()
                else:
                    module.start()
            
            info.state = ModuleState.RUNNING
            info.started_at = datetime.now()
            info.error = None
            
            self.logger.info(f"Módulo iniciado: {name}")
            return True
            
        except Exception as e:
            info.state = ModuleState.FAILED
            info.error = str(e)
            self.logger.error(f"Erro ao iniciar {name}: {e}")
            return False
    
    def _check_dependencies(self, name: str) -> bool:
        """Verifica se todas as dependências estão running."""
        info = self._modules[name]
        
        for dep in info.dependencies:
            if dep not in self._modules:
                self.logger.error(f"Dependência {dep} não registrada para {name}")
                return False
            
            dep_info = self._modules[dep]
            if dep_info.state != ModuleState.RUNNING:
                self.logger.error(f"Dependência {dep} não está running para {name}")
                return False
        
        return True
    
    async def pause(self, name: str) -> bool:
        """Pausa um módulo."""
        if name not in self._modules:
            return False
        
        info = self._modules[name]
        if info.state != ModuleState.RUNNING:
            return False
        
        try:
            module = info.module
            if hasattr(module, "pause"):
                if asyncio.iscoroutinefunction(module.pause):
                    await module.pause()
                else:
                    module.pause()
            
            info.state = ModuleState.PAUSED
            self.logger.info(f"Módulo pausado: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao pausar {name}: {e}")
            return False
    
    async def resume(self, name: str) -> bool:
        """Retoma um módulo pausado."""
        if name not in self._modules:
            return False
        
        info = self._modules[name]
        if info.state != ModuleState.PAUSED:
            return False
        
        try:
            module = info.module
            if hasattr(module, "resume"):
                if asyncio.iscoroutinefunction(module.resume):
                    await module.resume()
                else:
                    module.resume()
            
            info.state = ModuleState.RUNNING
            self.logger.info(f"Módulo retomado: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao retomar {name}: {e}")
            return False
    
    async def stop(self, name: str) -> bool:
        """Para um módulo."""
        if name not in self._modules:
            return False
        
        info = self._modules[name]
        
        try:
            self.logger.debug(f"Parando módulo: {name}")
            
            module = info.module
            if hasattr(module, "shutdown"):
                if asyncio.iscoroutinefunction(module.shutdown):
                    await module.shutdown()
                else:
                    module.shutdown()
            
            info.state = ModuleState.STOPPED
            info.stopped_at = datetime.now()
            
            self.logger.info(f"Módulo parado: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao parar {name}: {e}")
            info.state = ModuleState.FAILED
            info.error = str(e)
            return False
    
    async def stop_all(self) -> None:
        """Para todos os módulos (ordem reversa)."""
        self.logger.info("Parando todos os módulos...")
        
        for name in reversed(self._startup_order):
            await self.stop(name)
    
    async def restart(self, name: str) -> bool:
        """Reinicia um módulo."""
        if name not in self._modules:
            return False
        
        if not await self.stop(name):
            return False
        
        # Aguarda um pouco
        await asyncio.sleep(1)
        
        if not await self._initialize_module(name):
            return False
        
        return await self._start_module(name)
    
    def get_state(self, name: str) -> Optional[ModuleState]:
        """Obtém estado de um módulo."""
        info = self._modules.get(name)
        return info.state if info else None
    
    def get_module_info(self, name: str) -> Optional[ModuleInfo]:
        """Obtém informações de um módulo."""
        return self._modules.get(name)
    
    def list_modules(self) -> List[str]:
        """Lista todos os módulos registrados."""
        return list(self._modules.keys())
    
    def list_by_state(self, state: ModuleState) -> List[str]:
        """Lista módulos por estado."""
        return [name for name, info in self._modules.items() if info.state == state]
    
    def get_status_report(self) -> Dict[str, Any]:
        """Gera relatório de status."""
        return {
            "total": len(self._modules),
            "states": {
                state.name: len([m for m in self._modules.values() if m.state == state])
                for state in ModuleState
            },
            "modules": {
                name: {
                    "state": info.state.name,
                    "dependencies": info.dependencies,
                    "error": info.error
                }
                for name, info in self._modules.items()
            }
        }