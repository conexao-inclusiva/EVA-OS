"""Contexto para ferramentas."""

from typing import Dict, Any, Optional
from datetime import datetime


class ToolContext:
    """
    Gerencia o contexto para execução de ferramentas.
    """
    
    def __init__(self, tool_manager):
        self.tool_manager = tool_manager
        self.logger = tool_manager.logger
    
    def get_context(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Obtém contexto para uma ferramenta.
        """
        return {
            "tool": tool_name,
            "params": params,
            "timestamp": datetime.now().isoformat()
        }
    
    def enrich_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enriquece o contexto com informações adicionais.
        """
        enriched = context.copy()
        
        if "user" not in enriched:
            enriched["user"] = {"role": "guest"}
        
        if "timestamp" not in enriched:
            enriched["timestamp"] = datetime.now().isoformat()
        
        return enriched