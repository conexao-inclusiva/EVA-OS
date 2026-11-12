"""Contexto temporal."""

from typing import Dict, Any, Optional
from datetime import datetime, time, timedelta
import calendar


class TemporalContext:
    """
    Contexto temporal.
    
    Mantém:
    - Data e hora atual
    - Período do dia (manhã, tarde, noite, madrugada)
    - Dia da semana
    - Fim de semana ou dia útil
    - Rotina escolar
    - Férias
    - Aniversários
    - Eventos importantes
    """
    
    def __init__(self):
        self._data: Dict[str, Any] = {
            "timestamp": None,
            "date": None,
            "time": None,
            "period": None,  # dawn, morning, afternoon, evening, night
            "day_of_week": None,  # 0-6 (segunda=0)
            "day_name": None,
            "is_weekend": False,
            "is_holiday": False,
            "is_vacation": False,
            "is_school_day": True,
            "season": None,
            "year": None,
            "month": None,
            "day": None,
            "hour": None,
            "minute": None,
            "last_update": None
        }
        
        # Períodos
        self._periods = {
            "dawn": (0, 5),      # 00:00 - 05:59
            "morning": (6, 11),  # 06:00 - 11:59
            "afternoon": (12, 17), # 12:00 - 17:59
            "evening": (18, 20), # 18:00 - 20:59
            "night": (21, 23)    # 21:00 - 23:59
        }
        
        # Dias da semana em português
        self._weekday_names = [
            "segunda-feira",
            "terça-feira",
            "quarta-feira",
            "quinta-feira",
            "sexta-feira",
            "sábado",
            "domingo"
        ]
        
        # Estações do ano (Sul)
        self._seasons = {
            (1, 2): "verão",
            (3, 4, 5): "outono",
            (6, 7, 8): "inverno",
            (9, 10, 11): "primavera",
            (12,): "verão"
        }
    
    def update(self) -> None:
        """Atualiza o contexto temporal com a data/hora atual."""
        now = datetime.now()
        self._data["timestamp"] = now.isoformat()
        self._data["date"] = now.strftime("%Y-%m-%d")
        self._data["time"] = now.strftime("%H:%M:%S")
        self._data["year"] = now.year
        self._data["month"] = now.month
        self._data["day"] = now.day
        self._data["hour"] = now.hour
        self._data["minute"] = now.minute
        
        # Período do dia
        self._data["period"] = self._get_period(now.hour)
        
        # Dia da semana
        weekday = now.weekday()  # 0=segunda, 6=domingo
        self._data["day_of_week"] = weekday
        self._data["day_name"] = self._weekday_names[weekday]
        self._data["is_weekend"] = weekday in [5, 6]  # sábado=5, domingo=6
        
        # Estação
        self._data["season"] = self._get_season(now.month)
        
        # Horário escolar (dias úteis, 7-17h)
        self._data["is_school_day"] = (
            not self._data["is_weekend"] and
            7 <= now.hour < 17
        )
        
        self._data["last_update"] = datetime.now()
    
    def _get_period(self, hour: int) -> str:
        """Determina o período do dia com base na hora."""
        for period, (start, end) in self._periods.items():
            if start <= hour <= end:
                return period
        return "unknown"
    
    def _get_season(self, month: int) -> str:
        """Determina a estação do ano (Hemisferio Sul)."""
        for months, season in self._seasons.items():
            if month in months:
                return season
        return "unknown"
    
    def get_period(self) -> str:
        """Obtém o período atual."""
        return self._data.get("period", "unknown")
    
    def is_weekend(self) -> bool:
        """Verifica se é fim de semana."""
        return self._data.get("is_weekend", False)
    
    def is_school_day(self) -> bool:
        """Verifica se é dia de escola."""
        return self._data.get("is_school_day", True)
    
    def get_time_until(self, target_hour: int, target_minute: int = 0) -> float:
        """Tempo em horas até um horário específico."""
        now = datetime.now()
        target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds() / 3600
    
    def is_between(self, start_hour: int, end_hour: int) -> bool:
        """Verifica se a hora atual está entre dois horários."""
        now = datetime.now()
        start = now.replace(hour=start_hour, minute=0, second=0)
        end = now.replace(hour=end_hour, minute=0, second=0)
        if end < start:
            end += timedelta(days=1)
        return start <= now <= end
    
    def set(self, key: str, value: Any) -> None:
        """Define um valor no contexto."""
        self._data[key] = value
        self._data["last_update"] = datetime.now()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obtém um valor do contexto."""
        return self._data.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """Obtém todo o contexto."""
        self.update()  # Atualiza antes de retornar
        return self._data.copy()