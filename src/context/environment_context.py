"""Contexto do ambiente."""

from typing import Dict, Any, Optional, List
from datetime import datetime


class EnvironmentContext:
    """
    Contexto do ambiente físico e digital.
    
    Mantém:
    - Localização
    - Dispositivos e sensores
    - Estado da casa
    - Temperatura, luzes, etc.
    """
    
    def __init__(self):
        self._data: Dict[str, Any] = {
            "location": "Casa",
            "room": None,
            "devices": {},
            "sensors": {},
            "lights": {},
            "temperature": 0.0,
            "humidity": 0.0,
            "weather": {
                "temp": 0.0,
                "condition": "unknown",
                "humidity": 0.0
            },
            "network_status": "unknown",
            "server_status": "unknown",
            "energy": {
                "consumption": 0.0,
                "solar_production": 0.0,
                "battery_level": 0.0
            },
            "last_update": None
        }
    
    def set_room(self, room: str) -> None:
        """Define a sala atual."""
        self._data["room"] = room
        self._data["last_update"] = datetime.now()
    
    def get_room(self) -> Optional[str]:
        """Obtém a sala atual."""
        return self._data.get("room")
    
    def set_device(self, device_id: str, status: Dict[str, Any]) -> None:
        """Define o estado de um dispositivo."""
        if "devices" not in self._data:
            self._data["devices"] = {}
        self._data["devices"][device_id] = {
            **status,
            "last_update": datetime.now().isoformat()
        }
        self._data["last_update"] = datetime.now()
    
    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Obtém o estado de um dispositivo."""
        return self._data.get("devices", {}).get(device_id)
    
    def get_devices(self) -> Dict[str, Any]:
        """Obtém todos os dispositivos."""
        return self._data.get("devices", {})
    
    def set_sensor(self, sensor_id: str, value: Any) -> None:
        """Define o valor de um sensor."""
        if "sensors" not in self._data:
            self._data["sensors"] = {}
        self._data["sensors"][sensor_id] = {
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
        self._data["last_update"] = datetime.now()
        
        # Atualiza atalhos
        if sensor_id == "temperature":
            self._data["temperature"] = value
        elif sensor_id == "humidity":
            self._data["humidity"] = value
    
    def get_sensor(self, sensor_id: str) -> Optional[Any]:
        """Obtém o valor de um sensor."""
        sensor = self._data.get("sensors", {}).get(sensor_id)
        return sensor.get("value") if sensor else None
    
    def get_sensors(self) -> Dict[str, Any]:
        """Obtém todos os sensores."""
        return self._data.get("sensors", {})
    
    def set_light(self, light_id: str, status: bool) -> None:
        """Define o estado de uma luz."""
        if "lights" not in self._data:
            self._data["lights"] = {}
        self._data["lights"][light_id] = {
            "on": status,
            "last_update": datetime.now().isoformat()
        }
        self._data["last_update"] = datetime.now()
    
    def get_light(self, light_id: str) -> Optional[bool]:
        """Obtém o estado de uma luz."""
        light = self._data.get("lights", {}).get(light_id)
        return light.get("on") if light else None
    
    def set_temperature(self, temp: float) -> None:
        """Define a temperatura."""
        self._data["temperature"] = temp
        self._data["last_update"] = datetime.now()
    
    def set_weather(self, weather: Dict[str, Any]) -> None:
        """Define o clima."""
        self._data["weather"] = weather
        self._data["last_update"] = datetime.now()
    
    def set(self, key: str, value: Any) -> None:
        """Define um valor no contexto."""
        self._data[key] = value
        self._data["last_update"] = datetime.now()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obtém um valor do contexto."""
        return self._data.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """Obtém todo o contexto."""
        result = self._data.copy()
        return result