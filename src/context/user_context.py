"""Contexto do usuário."""

from typing import Dict, Any, Optional, List
from datetime import datetime


class UserContext:
    """
    Contexto do usuário.
    
    Mantém:
    - Quem está falando
    - Permissões do usuário
    - Preferências
    - Perfil
    - Histórico de interações
    """
    
    def __init__(self):
        self._data: Dict[str, Any] = {
            "current_user": None,
            "users": {},  # user_id -> user_data
            "active_users": [],
            "last_interaction": None
        }
        
        # Usuários padrão
        self._init_default_users()
    
    def _init_default_users(self) -> None:
        """Inicializa usuários padrão."""
        self._data["users"] = {
            "alberto": {
                "name": "Alberto",
                "role": "admin",
                "preferences": {
                    "voice": True,
                    "language": "pt-BR",
                    "lights_auto": False,
                    "temperature": 22.0,
                    "notifications": True
                },
                "profile": {
                    "age": 35,
                    "occupation": "Engenheiro de Software",
                    "interests": ["programação", "eletrônica", "IA"]
                }
            },
            "juliana": {
                "name": "Juliana",
                "role": "user",
                "preferences": {
                    "voice": True,
                    "language": "pt-BR",
                    "lights_auto": True,
                    "temperature": 24.0,
                    "notifications": True
                },
                "profile": {
                    "age": 32,
                    "occupation": "Designer",
                    "interests": ["design", "arte", "fotografia"]
                }
            },
            "nicolas": {
                "name": "Nicolas",
                "role": "child",
                "preferences": {
                    "voice": True,
                    "language": "pt-BR",
                    "lights_auto": False,
                    "temperature": 24.0,
                    "notifications": False
                },
                "profile": {
                    "age": 7,
                    "occupation": "Estudante",
                    "interests": ["jogos", "desenhos", "robôs"]
                }
            }
        }
    
    def set_current_user(self, user_id: str) -> None:
        """Define o usuário atual."""
        if user_id in self._data["users"]:
            self._data["current_user"] = user_id
            if user_id not in self._data["active_users"]:
                self._data["active_users"].append(user_id)
            self._data["last_interaction"] = datetime.now()
    
    def get_current_user(self) -> Optional[str]:
        """Obtém o usuário atual."""
        return self._data.get("current_user")
    
    def get_current_user_data(self) -> Optional[Dict[str, Any]]:
        """Obtém os dados do usuário atual."""
        user_id = self.get_current_user()
        if user_id:
            return self._data["users"].get(user_id)
        return None
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Obtém dados de um usuário."""
        return self._data["users"].get(user_id)
    
    def get_user_preference(self, user_id: str, key: str, default: Any = None) -> Any:
        """Obtém uma preferência de um usuário."""
        user = self.get_user(user_id)
        if user:
            return user.get("preferences", {}).get(key, default)
        return default
    
    def get_user_role(self, user_id: str) -> str:
        """Obtém o papel de um usuário."""
        user = self.get_user(user_id)
        if user:
            return user.get("role", "guest")
        return "guest"
    
    def has_permission(self, user_id: str, permission: str) -> bool:
        """Verifica se um usuário tem uma permissão."""
        role = self.get_user_role(user_id)
        
        # Mapeamento de papéis para permissões
        role_permissions = {
            "admin": ["all"],
            "user": ["conversation", "control_lights", "control_temperature", "set_reminders"],
            "child": ["conversation", "play_music", "set_reminders"],
            "guest": ["conversation"]
        }
        
        perms = role_permissions.get(role, [])
        return "all" in perms or permission in perms
    
    def set_user_preference(self, user_id: str, key: str, value: Any) -> None:
        """Define uma preferência de um usuário."""
        if user_id in self._data["users"]:
            if "preferences" not in self._data["users"][user_id]:
                self._data["users"][user_id]["preferences"] = {}
            self._data["users"][user_id]["preferences"][key] = value
    
    def get_all_users(self) -> List[str]:
        """Lista todos os usuários."""
        return list(self._data["users"].keys())
    
    def get_active_users(self) -> List[str]:
        """Lista usuários ativos."""
        return self._data.get("active_users", [])
    
    def set(self, key: str, value: Any) -> None:
        """Define um valor no contexto."""
        self._data[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obtém um valor do contexto."""
        return self._data.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """Obtém todo o contexto."""
        result = self._data.copy()
        # Remove dados sensíveis em produção
        # result["users"] = {k: v for k, v in result.get("users", {}).items()}
        return result