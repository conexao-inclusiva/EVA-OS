"""Gerenciador de Clima da EVA."""

import aiohttp
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
from pathlib import Path

from src.kernel.events import EventBus
from src.time.time_manager import TimeManager


class WeatherManager:
    """
    Gerenciador de Clima da EVA.
    
    Responsabilidades:
    - Previsão do tempo atual
    - Previsão para os próximos dias
    - Temperatura, condições, umidade
    - Clima por cidade
    """
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        self._running = False
        self._time_manager = None
        self._last_weather: Dict[str, Any] = {}
        self._default_city = self.config.get("weather.default_city", "Campinas")
        self._api_key = self.config.get("weather.api_key", "")
        
        self.logger.info("🌤️ [WeatherManager] Inicializado")
    
    async def initialize(self) -> None:
        self.logger.info("🌤️ [WeatherManager] Inicializando...")
        self._running = True
        self.logger.info("🌤️ [WeatherManager] Inicializado")
    
    async def get_current_weather(self, city: str = None) -> Dict[str, Any]:
        """
        Retorna a previsão do tempo atual.
        
        Args:
            city: Cidade (opcional, usa a padrão)
        """
        if not city:
            city = self._default_city
        
        # Tenta API
        weather = await self._fetch_from_api(city)
        
        # Fallback: dados simulados
        if not weather:
            weather = self._get_fallback_weather(city)
        
        self._last_weather[city] = weather
        return weather
    
    async def _fetch_from_api(self, city: str) -> Optional[Dict[str, Any]]:
        """Busca clima via API (OpenWeatherMap)."""
        try:
            if not self._api_key:
                return None
            
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": city,
                "appid": self._api_key,
                "units": "metric",
                "lang": "pt_br"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        return {
                            "city": data.get("name", city),
                            "country": data.get("sys", {}).get("country", ""),
                            "temperature": data.get("main", {}).get("temp", 0),
                            "feels_like": data.get("main", {}).get("feels_like", 0),
                            "humidity": data.get("main", {}).get("humidity", 0),
                            "pressure": data.get("main", {}).get("pressure", 0),
                            "description": data.get("weather", [{}])[0].get("description", ""),
                            "icon": data.get("weather", [{}])[0].get("icon", ""),
                            "wind_speed": data.get("wind", {}).get("speed", 0),
                            "timestamp": datetime.now().isoformat()
                        }
        
        except Exception as e:
            self.logger.error(f"Erro ao buscar clima: {e}")
        
        return None
    
    async def get_forecast(self, city: str = None, days: int = 5) -> List[Dict[str, Any]]:
        """Retorna a previsão para os próximos dias."""
        if not city:
            city = self._default_city
        
        # Tenta API
        forecast = await self._fetch_forecast_from_api(city, days)
        
        # Fallback
        if not forecast:
            forecast = self._get_fallback_forecast(city, days)
        
        return forecast
    
    async def _fetch_forecast_from_api(self, city: str, days: int) -> Optional[List[Dict[str, Any]]]:
        """Busca previsão via API."""
        try:
            if not self._api_key:
                return None
            
            url = "https://api.openweathermap.org/data/2.5/forecast"
            params = {
                "q": city,
                "appid": self._api_key,
                "units": "metric",
                "lang": "pt_br",
                "cnt": days * 8  # 8 previsões por dia
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        forecast_list = data.get("list", [])
                        
                        result = []
                        for item in forecast_list[:days]:
                            result.append({
                                "date": item.get("dt_txt", ""),
                                "temperature": item.get("main", {}).get("temp", 0),
                                "description": item.get("weather", [{}])[0].get("description", ""),
                                "icon": item.get("weather", [{}])[0].get("icon", "")
                            })
                        
                        return result
        
        except Exception as e:
            self.logger.error(f"Erro ao buscar previsão: {e}")
        
        return None
    
    def _get_fallback_weather(self, city: str) -> Dict[str, Any]:
        """Retorna dados de clima simulados (fallback)."""
        import random
        
        conditions = ["ensolarado", "parcialmente nublado", "nublado", "chuvoso", "trovoada"]
        temps = list(range(15, 35))
        
        return {
            "city": city,
            "country": "BR",
            "temperature": random.choice(temps),
            "feels_like": random.choice(temps),
            "humidity": random.randint(40, 90),
            "pressure": random.randint(1000, 1020),
            "description": random.choice(conditions),
            "icon": "01d",
            "wind_speed": random.randint(0, 30),
            "timestamp": datetime.now().isoformat(),
            "fallback": True
        }
    
    def _get_fallback_forecast(self, city: str, days: int) -> List[Dict[str, Any]]:
        """Retorna previsão simulada (fallback)."""
        import random
        
        conditions = ["ensolarado", "parcialmente nublado", "nublado", "chuvoso"]
        result = []
        
        for i in range(days):
            date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
            result.append({
                "date": date,
                "temperature": random.randint(15, 35),
                "description": random.choice(conditions),
                "icon": "01d"
            })
        
        return result
    
    async def shutdown(self) -> None:
        self.logger.info("🌤️ [WeatherManager] Desligando...")
        self._running = False
        self.logger.info("🌤️ [WeatherManager] Desligado")
    
    async def health_check(self) -> dict:
        return {
            "status": "running" if self._running else "stopped",
            "default_city": self._default_city,
            "has_api_key": bool(self._api_key)
        }


from datetime import timedelta