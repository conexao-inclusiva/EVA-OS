"""Registro central de ferramentas."""

from typing import Dict, Type, Optional, List, Any

from src.tools.base_tool import BaseTool


class ToolRegistry:
    """
    Registro central de todas as ferramentas disponíveis.
    """
    
    def __init__(self):
        self._tools: Dict[str, Type[BaseTool]] = {}
        self._tool_metadata: Dict[str, Dict[str, Any]] = {}
    
    def register(self, name: str, tool_class: Type[BaseTool],
                 metadata: Dict[str, Any] = None) -> None:
        """
        Registra uma ferramenta.
        
        Args:
            name: Nome da ferramenta
            tool_class: Classe da ferramenta
            metadata: Metadados adicionais
        """
        self._tools[name] = tool_class
        self._tool_metadata[name] = {
            "name": name,
            "class": tool_class.__name__,
            "module": tool_class.__module__,
            "capabilities": getattr(tool_class, "__plugin_capabilities__", ["general"]),
            "permissions": getattr(tool_class, "__plugin_permissions__", []),
            "version": getattr(tool_class, "__plugin_version__", "1.0.0"),
            "description": getattr(tool_class, "__plugin_description__", ""),
            **(metadata or {})
        }
    
    def get(self, name: str) -> Optional[Type[BaseTool]]:
        """Obtém uma classe de ferramenta pelo nome."""
        return self._tools.get(name)
    
    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """Obtém metadados de uma ferramenta."""
        return self._tool_metadata.get(name)
    
    def list(self) -> List[str]:
        """Lista todas as ferramentas registradas."""
        return list(self._tools.keys())
    
    def list_with_metadata(self) -> List[Dict[str, Any]]:
        """Lista todas as ferramentas com metadados."""
        return list(self._tool_metadata.values())
    
    def get_by_capability(self, capability: str) -> List[str]:
        """Obtém ferramentas com uma capacidade específica."""
        result = []
        for name, meta in self._tool_metadata.items():
            if capability in meta.get("capabilities", []):
                result.append(name)
        return result
    
    def get_by_permission(self, permission: str) -> List[str]:
        """Obtém ferramentas que requerem uma permissão específica."""
        result = []
        for name, meta in self._tool_metadata.items():
            if permission in meta.get("permissions", []):
                result.append(name)
        return result
    
    def unregister(self, name: str) -> bool:
        """Remove uma ferramenta do registro."""
        if name in self._tools:
            del self._tools[name]
            if name in self._tool_metadata:
                del self._tool_metadata[name]
            return True
        return False
    
    def clear(self) -> None:
        """Limpa o registro."""
        self._tools.clear()
        self._tool_metadata.clear()