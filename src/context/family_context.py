"""Contexto da família."""

from typing import Dict, Any, List, Optional
from datetime import datetime


class FamilyContext:
    """Contexto sobre a família."""
    
    def __init__(self):
        self._data = {
            "members": [],
            "current_member": None,
            "family_events": [],
            "family_values": [],
            "active_members": []
        }
    
    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._data["last_update"] = datetime.now()
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)
    
    def add_member(self, name: str) -> None:
        if name not in self._data["members"]:
            self._data["members"].append(name)
    
    def set_current_member(self, name: str) -> None:
        self._data["current_member"] = name
        if name not in self._data["active_members"]:
            self._data["active_members"].append(name)
    
    def get_all(self) -> Dict[str, Any]:
        return self._data.copy()