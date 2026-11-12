"""Registro central de agentes."""

from typing import Dict, Type, Optional, List, Any

from src.agents.base_agent import BaseAgent


class AgentRegistry:
    """
    Registro central de todos os agentes disponíveis.
    """
    
    def __init__(self):
        self._agents: Dict[str, Type[BaseAgent]] = {}
        self._agent_metadata: Dict[str, Dict[str, Any]] = {}
    
    def register(self, name: str, agent_class: Type[BaseAgent],
                 metadata: Dict[str, Any] = None) -> None:
        """
        Registra um agente.
        
        Args:
            name: Nome do agente
            agent_class: Classe do agente
            metadata: Metadados adicionais
        """
        self._agents[name] = agent_class
        self._agent_metadata[name] = {
            "name": name,
            "class": agent_class.__name__,
            "module": agent_class.__module__,
            "capabilities": getattr(agent_class, "__plugin_capabilities__", ["general"]),
            "version": getattr(agent_class, "__plugin_version__", "1.0.0"),
            "description": getattr(agent_class, "__plugin_description__", ""),
            **(metadata or {})
        }
    
    def get(self, name: str) -> Optional[Type[BaseAgent]]:
        """Obtém uma classe de agente pelo nome."""
        return self._agents.get(name)
    
    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """Obtém metadados de um agente."""
        return self._agent_metadata.get(name)
    
    def list(self) -> List[str]:
        """Lista todos os agentes registrados."""
        return list(self._agents.keys())
    
    def list_with_metadata(self) -> List[Dict[str, Any]]:
        """Lista todos os agentes com metadados."""
        return list(self._agent_metadata.values())
    
    def get_by_capability(self, capability: str) -> List[str]:
        """Obtém agentes com uma capacidade específica."""
        result = []
        for name, meta in self._agent_metadata.items():
            if capability in meta.get("capabilities", []):
                result.append(name)
        return result
    
    def unregister(self, name: str) -> bool:
        """Remove um agente do registro."""
        if name in self._agents:
            del self._agents[name]
            if name in self._agent_metadata:
                del self._agent_metadata[name]
            return True
        return False
    
    def clear(self) -> None:
        """Limpa o registro."""
        self._agents.clear()
        self._agent_metadata.clear()