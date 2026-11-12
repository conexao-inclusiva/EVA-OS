"""Classe base para todas as ferramentas da EVA."""

from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from datetime import datetime


class BaseTool(ABC):
    """
    Classe base para todas as ferramentas.
    
    Toda ferramenta deve herdar desta classe e implementar:
    - execute(): Execução da ferramenta
    - validate(): Validação de parâmetros
    - get_info(): Informações da ferramenta
    """
    
    # Atributos de plugin
    __plugin_name__ = "base_tool"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Ferramenta base da EVA"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["tool", "base"]
    __plugin_capabilities__ = ["base"]
    __plugin_requires__ = ["logger", "config"]
    
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.name = self.__class__.__name__.lower().replace("tool", "")
        self._execution_count = 0
        self._error_count = 0
        self._last_execution: Optional[datetime] = None
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executa a ferramenta.
        
        Args:
            params: Parâmetros da execução
            context: Contexto adicional
            
        Returns:
            Dict com resultado da execução
        """
        pass
    
    @abstractmethod
    def validate(self, params: Dict[str, Any]) -> bool:
        """
        Valida os parâmetros da ferramenta.
        
        Returns:
            True se válido, False caso contrário
        """
        pass
    
    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """
        Retorna informações da ferramenta.
        """
        pass
    
    def get_required_params(self) -> List[str]:
        """Retorna lista de parâmetros obrigatórios."""
        return []
    
    def get_optional_params(self) -> Dict[str, Any]:
        """Retorna parâmetros opcionais com valores padrão."""
        return {}
    
    def get_capabilities(self) -> List[str]:
        """Retorna capacidades da ferramenta."""
        return getattr(self, "__plugin_capabilities__", ["general"])
    
    def get_permissions(self) -> List[str]:
        """Retorna permissões necessárias."""
        return getattr(self, "__plugin_permissions__", [])
    
    def can_handle(self, action: str) -> bool:
        """Verifica se a ferramenta pode lidar com uma ação."""
        return action in self.get_capabilities() or "general" in self.get_capabilities()
    
    async def execute_with_validation(self, params: Dict[str, Any], 
                                      context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executa com validação prévia.
        """
        # Valida parâmetros
        if not self.validate(params):
            return {
                "success": False,
                "error": "Validação de parâmetros falhou",
                "tool": self.name,
                "timestamp": datetime.now().isoformat()
            }
        
        # Verifica parâmetros obrigatórios
        for req in self.get_required_params():
            if req not in params:
                return {
                    "success": False,
                    "error": f"Parâmetro obrigatório ausente: {req}",
                    "tool": self.name,
                    "timestamp": datetime.now().isoformat()
                }
        
        # Executa
        try:
            result = await self.execute(params, context or {})
            self._execution_count += 1
            self._last_execution = datetime.now()
            result["success"] = True
            result["tool"] = self.name
            result["timestamp"] = datetime.now().isoformat()
            return result
        except Exception as e:
            self._error_count += 1
            self.logger.error(f"Erro na ferramenta {self.name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool": self.name,
                "timestamp": datetime.now().isoformat()
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas da ferramenta."""
        return {
            "name": self.name,
            "execution_count": self._execution_count,
            "error_count": self._error_count,
            "last_execution": self._last_execution.isoformat() if self._last_execution else None,
            "capabilities": self.get_capabilities()
        }