"""Gerenciador de Tempo da EVA."""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import calendar
import requests
import json

from src.kernel.events import EventBus


class TimeManager:
    """
    Gerenciador de Tempo da EVA.
    
    Responsabilidades:
    - Data e hora atual
    - Conversão de fuso horário
    - Formatação de data/hora
    - Cálculo de dias úteis
    """
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        self._timezone = self.config.get("time.timezone", "America/Sao_Paulo")
        self._running = False
        self._current_time = None
        
        # Dias da semana em português
        self._weekdays_pt = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
        self._months_pt = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                          "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        
        self.logger.info("🕐 [TimeManager] Inicializado")
    
    async def initialize(self) -> None:
        self.logger.info("🕐 [TimeManager] Inicializando...")
        self._running = True
        
        # Atualiza a hora
        self._update_time()
        
        self.logger.info("🕐 [TimeManager] Inicializado")
    
    def _update_time(self) -> None:
        """Atualiza a hora atual."""
        self._current_time = datetime.now()
    
    def get_current_time(self) -> Dict[str, Any]:
        """Retorna a data/hora atual formatada."""
        self._update_time()
        now = self._current_time
        
        return {
            "timestamp": now.isoformat(),
            "date": now.strftime("%d/%m/%Y"),
            "time": now.strftime("%H:%M:%S"),
            "hour": now.hour,
            "minute": now.minute,
            "year": now.year,
            "month": now.month,
            "month_name": self._months_pt[now.month - 1],
            "day": now.day,
            "weekday": now.weekday(),
            "weekday_name": self._weekdays_pt[now.weekday()],
            "is_weekend": now.weekday() >= 5,
            "is_workday": now.weekday() < 5,
            "day_of_year": now.timetuple().tm_yday
        }
    
    def get_formatted_time(self, format_type: str = "full") -> str:
        """
        Retorna a hora formatada.
        
        Args:
            format_type: "time", "date", "full", "short"
        """
        self._update_time()
        now = self._current_time
        
        if format_type == "time":
            return now.strftime("%H:%M")
        elif format_type == "date":
            return now.strftime("%d/%m/%Y")
        elif format_type == "short":
            return now.strftime("%d/%m %H:%M")
        else:
            return now.strftime("%A, %d de %B de %Y, %H:%M")
    
    def format_datetime(self, dt: datetime) -> str:
        """Formata uma data/hora específica."""
        return dt.strftime("%A, %d de %B de %Y, %H:%M")
    
    def get_date(self) -> str:
        """Retorna a data atual formatada."""
        self._update_time()
        return self._current_time.strftime("%d/%m/%Y")
    
    def get_time(self) -> str:
        """Retorna a hora atual formatada."""
        self._update_time()
        return self._current_time.strftime("%H:%M")
    
    def get_weekday(self) -> str:
        """Retorna o dia da semana atual em português."""
        self._update_time()
        return self._weekdays_pt[self._current_time.weekday()]
    
    def get_month_name(self) -> str:
        """Retorna o mês atual em português."""
        self._update_time()
        return self._months_pt[self._current_time.month - 1]
    
    def get_season(self) -> str:
        """Retorna a estação do ano atual (hemisfério sul)."""
        self._update_time()
        month = self._current_time.month
        
        if month in [12, 1, 2]:
            return "verão"
        elif month in [3, 4, 5]:
            return "outono"
        elif month in [6, 7, 8]:
            return "inverno"
        else:
            return "primavera"
    
    def get_part_of_day(self) -> str:
        """Retorna o período do dia."""
        self._update_time()
        hour = self._current_time.hour
        
        if 5 <= hour < 12:
            return "manhã"
        elif 12 <= hour < 18:
            return "tarde"
        elif 18 <= hour < 22:
            return "noite"
        else:
            return "madrugada"
    
    def get_greeting(self, name: str = None) -> str:
        """Retorna uma saudação baseada na hora do dia."""
        part = self.get_part_of_day()
        greetings = {
            "manhã": "Bom dia",
            "tarde": "Boa tarde",
            "noite": "Boa noite",
            "madrugada": "Boa madrugada"
        }
        greeting = greetings.get(part, "Olá")
        
        if name:
            return f"{greeting}, {name}!"
        return greeting
    
    def time_until(self, target_hour: int, target_minute: int = 0) -> timedelta:
        """Calcula o tempo até um horário específico."""
        self._update_time()
        now = self._current_time
        target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        
        if target <= now:
            target += timedelta(days=1)
        
        return target - now
    
    def is_between(self, start_hour: int, end_hour: int) -> bool:
        """Verifica se a hora atual está entre dois horários."""
        self._update_time()
        hour = self._current_time.hour
        return start_hour <= hour < end_hour
    
    async def shutdown(self) -> None:
        self.logger.info("🕐 [TimeManager] Desligando...")
        self._running = False
        self.logger.info("🕐 [TimeManager] Desligado")
    
    async def health_check(self) -> dict:
        return {
            "status": "running" if self._running else "stopped",
            "current_time": self.get_current_time()
        }