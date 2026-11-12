"""Gerenciador de versões."""

from typing import Dict, Any, List, Optional
from datetime import datetime


class VersionManager:
    """
    Gerencia versões do sistema.
    
    Responsabilidades:
    - Rastrear versões
    - Listar versões disponíveis
    - Comparar versões
    - Validar compatibilidade
    """
    
    def __init__(self, evolution_manager):
        self.evolution_manager = evolution_manager
        self.logger = evolution_manager.logger
        
        self._versions: List[Dict[str, Any]] = []
        self._current_version = "1.0.0"
        
        # Versões iniciais
        self._versions.append({
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "description": "Versão inicial",
            "changes": ["Sistema base"]
        })
    
    async def get_versions(self) -> List[Dict[str, Any]]:
        """
        Obtém lista de versões.
        """
        return self._versions
    
    async def get_current(self) -> str:
        """
        Obtém versão atual.
        """
        return self._current_version
    
    async def add_version(self, version: str, description: str, changes: List[str]) -> None:
        """
        Adiciona uma nova versão.
        """
        self._versions.append({
            "version": version,
            "timestamp": datetime.now().isoformat(),
            "description": description,
            "changes": changes
        })
        self._current_version = version
        self.logger.info(f"Nova versão: {version}")