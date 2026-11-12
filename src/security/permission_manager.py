"""Gerenciador de permissões do sistema."""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Set, Optional, Dict, Any
from uuid import uuid4


class Permission(Enum):
    """Permissões do sistema."""
    # Sistema
    SYSTEM_SHUTDOWN = auto()
    SYSTEM_RESTART = auto()
    SYSTEM_UPDATE = auto()
    SYSTEM_BACKUP = auto()
    
    # Kernel
    KERNEL_MODIFY = auto()
    KERNEL_READ = auto()
    
    # Arquivos
    FILE_READ = auto()
    FILE_WRITE = auto()
    FILE_DELETE = auto()
    FILE_EXECUTE = auto()
    
    # Rede
    NETWORK_READ = auto()
    NETWORK_MODIFY = auto()
    NETWORK_ADMIN = auto()
    
    # Dispositivos
    DEVICE_READ = auto()
    DEVICE_CONTROL = auto()
    DEVICE_ADMIN = auto()
    
    # Dados
    DATA_READ = auto()
    DATA_WRITE = auto()
    DATA_DELETE = auto()
    DATA_ADMIN = auto()
    
    # Agentes
    AGENT_CREATE = auto()
    AGENT_MODIFY = auto()
    AGENT_DELETE = auto()
    
    # Segurança
    SECURITY_READ = auto()
    SECURITY_MODIFY = auto()
    SECURITY_ADMIN = auto()
    
    # Auto-programação
    AUTOPROGRAM_RUN = auto()
    AUTOPROGRAM_MODIFY = auto()
    AUTOPROGRAM_ADMIN = auto()


@dataclass
class Role:
    """Papel com permissões associadas."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    permissions: Set[Permission] = field(default_factory=set)
    inherits_from: List[str] = field(default_factory=list)


@dataclass
class Policy:
    """Política de segurança."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    rules: Dict[str, Any] = field(default_factory=dict)


class PermissionManager:
    """
    Gerencia permissões do sistema EVA.
    Fundamental para a autoprogramação e segurança.
    """
    
    def __init__(self, logger, event_bus):
        self.logger = logger
        self.event_bus = event_bus
        
        self._roles: Dict[str, Role] = {}
        self._policies: Dict[str, Policy] = {}
        
        # Roles padrão
        self._init_default_roles()
    
    def _init_default_roles(self) -> None:
        """Inicializa roles padrão do sistema."""
        # Admin
        admin = Role(
            name="admin",
            description="Administrador completo do sistema"
        )
        admin.permissions = set(Permission)
        self._roles[admin.id] = admin
        
        # Usuário
        user = Role(
            name="user",
            description="Usuário padrão da família"
        )
        user.permissions = {
            Permission.FILE_READ,
            Permission.DATA_READ,
            Permission.DEVICE_READ,
            Permission.NETWORK_READ
        }
        self._roles[user.id] = user
        
        # Agente
        agent = Role(
            name="agent",
            description="Agente com permissões limitadas"
        )
        agent.permissions = {
            Permission.FILE_READ,
            Permission.DATA_READ,
            Permission.DATA_WRITE,
            Permission.NETWORK_READ,
            Permission.DEVICE_READ,
            Permission.DEVICE_CONTROL
        }
        self._roles[agent.id] = agent
        
        # Sistema
        system = Role(
            name="system",
            description="Componentes do sistema"
        )
        system.permissions = {
            Permission.SYSTEM_BACKUP,
            Permission.FILE_READ,
            Permission.FILE_WRITE,
            Permission.DATA_READ,
            Permission.DATA_WRITE,
            Permission.NETWORK_READ,
            Permission.DEVICE_READ,
            Permission.DEVICE_CONTROL
        }
        self._roles[system.id] = system
    
    def create_role(self, name: str, description: str = "") -> Role:
        """Cria um novo papel."""
        role = Role(
            name=name,
            description=description
        )
        self._roles[role.id] = role
        self.logger.info(f"Role criada: {name}")
        return role
    
    def add_permission(self, role_id: str, permission: Permission) -> bool:
        """Adiciona uma permissão a um papel."""
        if role_id not in self._roles:
            return False
        
        self._roles[role_id].permissions.add(permission)
        return True
    
    def remove_permission(self, role_id: str, permission: Permission) -> bool:
        """Remove uma permissão de um papel."""
        if role_id not in self._roles:
            return False
        
        if permission in self._roles[role_id].permissions:
            self._roles[role_id].permissions.remove(permission)
            return True
        return False
    
    def has_permission(self, role_id: str, permission: Permission) -> bool:
        """Verifica se um papel tem uma permissão."""
        if role_id not in self._roles:
            return False
        
        role = self._roles[role_id]
        
        # Verifica permissão diretamente
        if permission in role.permissions:
            return True
        
        # Verifica permissões herdadas
        for inherited_id in role.inherits_from:
            if self.has_permission(inherited_id, permission):
                return True
        
        return False
    
    def get_role(self, role_id: str) -> Optional[Role]:
        """Obtém um papel pelo ID."""
        return self._roles.get(role_id)
    
    def get_role_by_name(self, name: str) -> Optional[Role]:
        """Obtém um papel pelo nome."""
        for role in self._roles.values():
            if role.name == name:
                return role
        return None
    
    def list_roles(self) -> List[Role]:
        """Lista todos os papéis."""
        return list(self._roles.values())