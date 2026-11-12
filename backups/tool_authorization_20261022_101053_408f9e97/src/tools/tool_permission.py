"""Gerenciamento de permissões de ferramentas."""

from typing import Dict, Any, Optional, List


class ToolPermission:
    """
    Gerencia permissões para execução de ferramentas.
    """
    
    def __init__(self, tool_manager):
        self.tool_manager = tool_manager
        self.logger = tool_manager.logger
        
        # Mapeamento de roles para permissões
        self._role_permissions = {
            "admin": ["*"],
            "user": ["read", "execute", "basic"],
            "child": ["read", "basic"],
            "guest": ["read"]
        }
    
    def check(self, tool_name: str, context: Dict[str, Any]) -> bool:
        """
        Verifica se a ferramenta pode ser executada no contexto atual.
        """
        # Obtém permissões da ferramenta
        tool = self.tool_manager.get_tool(tool_name)
        if not tool:
            return False
        
        required_permissions = tool.get_permissions()
        
        # Se não requer permissões, permite
        if not required_permissions:
            return True
        
        # Obtém role do usuário
        user = context.get("user", {}).get("role", "guest")
        user_permissions = self._role_permissions.get(user, [])
        
        # Admin tem todas as permissões
        if "admin" in user_permissions or "*" in user_permissions:
            return True
        
        # Verifica cada permissão requerida
        for perm in required_permissions:
            if perm not in user_permissions:
                self.logger.warning(f"Permissão negada: {perm} para {tool_name}")
                return False
        
        return True
    
    def add_role_permission(self, role: str, permission: str) -> None:
        """Adiciona uma permissão a um role."""
        if role not in self._role_permissions:
            self._role_permissions[role] = []
        if permission not in self._role_permissions[role]:
            self._role_permissions[role].append(permission)
    
    def remove_role_permission(self, role: str, permission: str) -> None:
        """Remove uma permissão de um role."""
        if role in self._role_permissions and permission in self._role_permissions[role]:
            self._role_permissions[role].remove(permission)
    
    def get_role_permissions(self, role: str) -> List[str]:
        """Obtém permissões de um role."""
        return self._role_permissions.get(role, [])