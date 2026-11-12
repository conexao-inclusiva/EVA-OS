"""Registro de serviços do Core."""

from enum import Enum, auto
from typing import Any, Dict, List, Optional, Type


class ServiceStatus(Enum):
    """Status de um serviço."""
    REGISTERED = auto()
    INITIALIZED = auto()
    STARTING = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    FAILED = auto()


class Service:
    """Definição de um serviço registrado."""
    
    def __init__(self, name: str, instance: Any, dependencies: List[str] = None):
        self.name = name
        self.instance = instance
        self.dependencies = dependencies or []
        self.status = ServiceStatus.REGISTERED
        self.service_type = type(instance).__name__
        self.version = getattr(instance, "version", "0.0.1")
    
    def __repr__(self):
        return f"Service({self.name}, {self.service_type}, {self.status.name})"


class ServiceRegistry:
    """
    Catálogo central da EVA.
    Responde: Onde está o MemoryManager? Onde está o Planner?
    """
    
    def __init__(self, logger):
        self.logger = logger
        self._services: Dict[str, Service] = {}
        self._aliases: Dict[str, str] = {}
    
    def register(self, name: str, instance: Any, dependencies: List[str] = None) -> None:
        """
        Registra um serviço.
        
        Args:
            name: Nome único do serviço
            instance: Instância do serviço
            dependencies: Lista de nomes de serviços dos quais depende
        """
        if name in self._services:
            self.logger.warning(f"Serviço {name} já registrado. Substituindo...")
        
        service = Service(name, instance, dependencies)
        self._services[name] = service
        self.logger.info(f"Serviço registrado: {name} ({service.service_type})")
    
    def register_alias(self, alias: str, target: str) -> None:
        """Registra um alias para um serviço."""
        if target not in self._services:
            raise ValueError(f"Serviço alvo {target} não encontrado")
        self._aliases[alias] = target
        self.logger.debug(f"Alias registrado: {alias} -> {target}")
    
    def unregister(self, name: str) -> bool:
        """Remove um serviço do registro."""
        if name in self._services:
            del self._services[name]
            # Remove aliases
            self._aliases = {k: v for k, v in self._aliases.items() if v != name}
            self.logger.info(f"Serviço removido: {name}")
            return True
        return False
    
    def get(self, name: str) -> Optional[Any]:
        """
        Obtém um serviço pelo nome.
        Suporta aliases.
        """
        # Resolve alias
        actual_name = self._aliases.get(name, name)
        
        service = self._services.get(actual_name)
        if service:
            return service.instance
        return None
    
    def get_service(self, name: str) -> Optional[Service]:
        """Obtém o objeto Service completo."""
        actual_name = self._aliases.get(name, name)
        return self._services.get(actual_name)
    
    def exists(self, name: str) -> bool:
        """Verifica se um serviço existe."""
        actual_name = self._aliases.get(name, name)
        return actual_name in self._services
    
    def list(self) -> List[str]:
        """Lista todos os nomes de serviços registrados."""
        return list(self._services.keys())
    
    def list_services(self) -> List[Service]:
        """Lista todos os serviços registrados."""
        return list(self._services.values())
    
    def list_by_status(self, status: ServiceStatus) -> List[Service]:
        """Lista serviços por status."""
        return [s for s in self._services.values() if s.status == status]
    
    def get_status(self, name: str) -> Optional[ServiceStatus]:
        """Obtém status de um serviço."""
        service = self.get_service(name)
        return service.status if service else None
    
    def set_status(self, name: str, status: ServiceStatus) -> bool:
        """Define status de um serviço."""
        service = self.get_service(name)
        if not service:
            return False
        service.status = status
        self.logger.debug(f"Status do serviço {name}: {status.name}")
        return True
    
    def get_dependencies(self, name: str) -> List[str]:
        """Obtém dependências de um serviço."""
        service = self.get_service(name)
        return service.dependencies if service else []
    
    def get_dependents(self, name: str) -> List[str]:
        """Obtém serviços que dependem de um serviço."""
        dependents = []
        for service in self._services.values():
            if name in service.dependencies:
                dependents.append(service.name)
        return dependents
    
    def clear(self) -> None:
        """Limpa todos os serviços."""
        self._services.clear()
        self._aliases.clear()
        self.logger.info("ServiceRegistry limpo")