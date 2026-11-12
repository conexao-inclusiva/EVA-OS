"""Agente de Informação."""

from typing import Dict, Any, Optional
import subprocess
import platform
import psutil

from src.agents.base_agent import BaseAgent
from src.kernel.events import EventBus


class InformationAgent(BaseAgent):
    """
    Agente de Informação.
    
    Responsável por:
    - Informações do sistema
    - Status de serviços
    - Informações de rede
    - Dados de desempenho
    """
    
    __plugin_name__ = "information_agent"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Agente especializado em informações do sistema"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["agent", "information", "system"]
    __plugin_capabilities__ = ["information", "system_info", "status"]
    __plugin_requires__ = ["event_bus", "logger", "config"]
    
    def __init__(self, event_bus: EventBus, logger, config):
        super().__init__(event_bus, logger, config, name="information")
    
    async def process(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa uma tarefa de informação.
        """
        task_type = task.get("type", "system")
        
        if task_type == "system":
            return await self._handle_system_info(task)
        elif task_type == "network":
            return await self._handle_network_info(task)
        elif task_type == "resources":
            return await self._handle_resources(task)
        elif task_type == "services":
            return await self._handle_services(task)
        else:
            return {"error": f"Tipo de tarefa desconhecido: {task_type}"}
    
    async def _handle_system_info(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula informações do sistema."""
        return {
            "type": "system",
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "processor": platform.processor(),
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
    
    async def _handle_network_info(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula informações de rede."""
        # TODO: Implementar informações de rede completas
        return {
            "type": "network",
            "hostname": platform.node(),
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
    
    async def _handle_resources(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula informações de recursos."""
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "type": "resources",
            "cpu": cpu,
            "memory": {
                "percent": memory.percent,
                "used_gb": memory.used / (1024**3),
                "total_gb": memory.total / (1024**3)
            },
            "disk": {
                "percent": disk.percent,
                "used_gb": disk.used / (1024**3),
                "total_gb": disk.total / (1024**3)
            },
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
    
    async def _handle_services(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula informações de serviços."""
        # TODO: Implementar informações de serviços
        return {
            "type": "services",
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
    
    async def shutdown(self) -> None:
        """Desliga o agente."""
        await super().shutdown()
    
    async def health_check(self) -> Dict[str, Any]:
        """Verifica saúde do agente."""
        return await super().health_check()
    async def initialize(self) -> None:
        if self._initialized:
            return
        await super().initialize()

    async def start(self) -> None:
        if self._running:
            return
        if not self._initialized:
            raise RuntimeError("Agente nao inicializado")
        await super().start()
