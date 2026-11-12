"""Container de injeção de dependência."""

from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
from functools import wraps
import inspect


T = TypeVar('T')


class DependencyContainer:
    """
    Container para injeção de dependência.
    Nunca faremos: planner = Planner()
    Sempre: container.resolve("planner")
    """
    
    def __init__(self, logger, service_registry):
        self.logger = logger
        self.registry = service_registry
        
        # Fábricas de dependências
        self._factories: Dict[str, Callable] = {}
        
        # Instâncias singleton
        self._singletons: Dict[str, Any] = {}
        
        # Dependências em construção (detecção de ciclos)
        self._resolving: List[str] = []
    
    def register_factory(self, name: str, factory: Callable, dependencies: List[str] = None) -> None:
        """
        Registra uma fábrica para criar um serviço.
        """
        self._factories[name] = factory
        self.logger.debug(f"Fábrica registrada: {name}")
    
    def register_singleton(self, name: str, instance: Any) -> None:
        """
        Registra uma instância singleton.
        """
        self._singletons[name] = instance
        self.logger.debug(f"Singleton registrado: {name}")
    
    def resolve(self, name: str) -> Any:
        """
        Resolve uma dependência pelo nome.
        """
        # Verifica ciclos
        if name in self._resolving:
            raise RuntimeError(f"Ciclo de dependência detectado: {' -> '.join(self._resolving + [name])}")
        
        # 1. Verifica singleton
        if name in self._singletons:
            return self._singletons[name]
        
        # 2. Verifica registro no ServiceRegistry
        if self.registry.exists(name):
            return self.registry.get(name)
        
        # 3. Verifica fábrica
        if name in self._factories:
            self._resolving.append(name)
            try:
                instance = self._factories[name]()
                # Se retornou uma instância, registra como singleton
                if instance is not None:
                    self._singletons[name] = instance
                self._resolving.pop()
                return instance
            except Exception as e:
                self._resolving.pop()
                raise RuntimeError(f"Erro ao resolver dependência {name}: {e}")
        
        raise KeyError(f"Dependência não encontrada: {name}")
    
    def resolve_with_params(self, name: str, **params) -> Any:
        """
        Resolve uma dependência com parâmetros adicionais.
        """
        if name in self._factories:
            return self._factories[name](**params)
        
        raise KeyError(f"Fábrica não encontrada: {name}")
    
    def auto_inject(self, target_class: Type) -> Type:
        """
        Decorator para injeção automática de dependências.
        """
        original_init = target_class.__init__
        
        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            # Resolve dependências do __init__
            sig = inspect.signature(original_init)
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                if param_name in kwargs:
                    continue
                if param_name in self._singletons:
                    kwargs[param_name] = self._singletons[param_name]
                elif param_name in self._factories:
                    kwargs[param_name] = self.resolve(param_name)
                elif param.annotation != inspect.Parameter.empty:
                    # Tenta resolver pelo tipo
                    type_name = param.annotation.__name__.lower()
                    if self.exists(type_name):
                        kwargs[param_name] = self.resolve(type_name)
            
            original_init(self, *args, **kwargs)
        
        target_class.__init__ = new_init
        return target_class
    
    def exists(self, name: str) -> bool:
        """Verifica se uma dependência pode ser resolvida."""
        return (
            name in self._singletons or
            name in self._factories or
            self.registry.exists(name)
        )
    
    def clear(self) -> None:
        """Limpa o container."""
        self._factories.clear()
        self._singletons.clear()
        self._resolving.clear()
        self.logger.info("DependencyContainer limpo")