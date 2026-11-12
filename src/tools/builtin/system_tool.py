"""Ferramenta de operações do sistema."""

from typing import Dict, Any, Optional, List
import psutil
import platform
import os

from src.tools.base_tool import BaseTool


class SystemTool(BaseTool):
    """
    Operações do sistema (info, processo, etc).
    """
    
    __plugin_name__ = "system_tool"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Operações do sistema"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["tool", "system", "info"]
    __plugin_capabilities__ = ["system", "info"]
    __plugin_permissions__ = ["read", "system"]
    __plugin_requires__ = ["logger", "config"]
    
    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "Operações do sistema",
            "capabilities": ["system", "info"]
        }
    
    def get_required_params(self) -> List[str]:
        return ["action"]
    
    def validate(self, params: Dict[str, Any]) -> bool:
        if "action" not in params:
            return False
        return params["action"] in ["info", "cpu", "memory", "disk", "processes"]
    
    async def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executa operação do sistema.
        """
        action = params["action"]
        
        result = {
            "type": "system",
            "action": action,
            "success": True
        }
        
        try:
            if action == "info":
                result["data"] = self._get_system_info()
            elif action == "cpu":
                result["data"] = self._get_cpu_info()
            elif action == "memory":
                result["data"] = self._get_memory_info()
            elif action == "disk":
                result["data"] = self._get_disk_info()
            elif action == "processes":
                result["data"] = self._get_process_info(params.get("limit", 10))
                
        except Exception as e:
            result["error"] = str(e)
            result["success"] = False
        
        return result
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Obtém informações do sistema."""
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "processor": platform.processor(),
            "cpus": psutil.cpu_count(),
            "uptime": (datetime.now() - datetime.fromtimestamp(psutil.boot_time())).total_seconds()
        }
    
    def _get_cpu_info(self) -> Dict[str, Any]:
        """Obtém informações de CPU."""
        return {
            "percent": psutil.cpu_percent(interval=0.5),
            "per_cpu": psutil.cpu_percent(interval=0.5, percpu=True),
            "count": psutil.cpu_count(),
            "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
        }
    
    def _get_memory_info(self) -> Dict[str, Any]:
        """Obtém informações de memória."""
        mem = psutil.virtual_memory()
        return {
            "total": mem.total,
            "available": mem.available,
            "percent": mem.percent,
            "used": mem.used,
            "free": mem.free
        }
    
    def _get_disk_info(self) -> Dict[str, Any]:
        """Obtém informações de disco."""
        disk = psutil.disk_usage('/')
        return {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        }
    
    def _get_process_info(self, limit: int) -> List[Dict[str, Any]]:
        """Obtém lista de processos."""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Ordena por uso de CPU
        processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
        return processes[:limit]

from datetime import datetime