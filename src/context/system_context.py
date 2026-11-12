"""Contexto do sistema."""

from typing import Dict, Any, Optional, List
from datetime import datetime


class SystemContext:
    """
    Contexto do sistema EVA.
    
    Mantém:
    - Estado interno da EVA
    - CPU, RAM, Disco
    - Serviços e containers
    - Banco de dados
    - Módulos ativos
    """
    
    def __init__(self):
        self._data: Dict[str, Any] = {
            "state": "OFFLINE",
            "version": "1.0.0",
            "uptime": 0,
            "memory_usage": 0.0,
            "cpu_usage": 0.0,
            "disk_usage": 0.0,
            "active_modules": [],
            "services": {},
            "last_boot": None,
            "errors": [],
            "warnings": [],
            "last_update": None
        }
    
    def set_state(self, state: str) -> None:
        """Define o estado do sistema."""
        self._data["state"] = state
        self._data["last_update"] = datetime.now()
    
    def get_state(self) -> str:
        """Obtém o estado do sistema."""
        return self._data.get("state", "UNKNOWN")
    
    def set_uptime(self, seconds: float) -> None:
        """Define o uptime do sistema."""
        self._data["uptime"] = seconds
        self._data["last_update"] = datetime.now()
    
    def set_resources(self, cpu: float, memory: float, disk: float) -> None:
        """Define o uso de recursos."""
        self._data["cpu_usage"] = cpu
        self._data["memory_usage"] = memory
        self._data["disk_usage"] = disk
        self._data["last_update"] = datetime.now()
    
    def add_module(self, module_name: str) -> None:
        """Adiciona um módulo ativo."""
        if module_name not in self._data["active_modules"]:
            self._data["active_modules"].append(module_name)
            self._data["last_update"] = datetime.now()
    
    def remove_module(self, module_name: str) -> None:
        """Remove um módulo ativo."""
        if module_name in self._data["active_modules"]:
            self._data["active_modules"].remove(module_name)
            self._data["last_update"] = datetime.now()
    
    def get_active_modules(self) -> List[str]:
        """Obtém módulos ativos."""
        return self._data.get("active_modules", [])
    
    def set_service_status(self, service_name: str, status: str) -> None:
        """Define o status de um serviço."""
        if "services" not in self._data:
            self._data["services"] = {}
        self._data["services"][service_name] = {
            "status": status,
            "last_update": datetime.now().isoformat()
        }
        self._data["last_update"] = datetime.now()
    
    def get_service_status(self, service_name: str) -> Optional[str]:
        """Obtém o status de um serviço."""
        service = self._data.get("services", {}).get(service_name)
        return service.get("status") if service else None
    
    def add_error(self, error: str) -> None:
        """Adiciona um erro."""
        self._data["errors"].append({
            "error": error,
            "timestamp": datetime.now().isoformat()
        })
        if len(self._data["errors"]) > 50:
            self._data["errors"] = self._data["errors"][-50:]
    
    def add_warning(self, warning: str) -> None:
        """Adiciona um aviso."""
        self._data["warnings"].append({
            "warning": warning,
            "timestamp": datetime.now().isoformat()
        })
        if len(self._data["warnings"]) > 50:
            self._data["warnings"] = self._data["warnings"][-50:]
    
    def set(self, key: str, value: Any) -> None:
        """Define um valor no contexto."""
        self._data[key] = value
        self._data["last_update"] = datetime.now()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obtém um valor do contexto."""
        return self._data.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """Obtém todo o contexto."""
        return self._data.copy()