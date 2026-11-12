"""Gerenciador de Calendário da EVA."""

import calendar
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, date
import json
from pathlib import Path

from src.kernel.events import EventBus
from src.time.time_manager import TimeManager


class CalendarManager:
    """
    Gerenciador de Calendário da EVA.
    
    Responsabilidades:
    - Calendário mensal
    - Feriados nacionais
    - Dias comemorativos
    - Eventos personalizados
    """
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        self._time_manager = None
        self._running = False
        
        # Feriados nacionais (fixos)
        self._holidays = {
            "01-01": "Ano Novo",
            "04-21": "Tiradentes",
            "05-01": "Dia do Trabalho",
            "09-07": "Independência do Brasil",
            "10-12": "Nossa Senhora Aparecida",
            "11-02": "Finados",
            "11-15": "Proclamação da República",
            "12-25": "Natal"
        }
        
        # Feriados móveis (calculados)
        self._moveable_holidays = {}
        
        # Eventos personalizados por usuário
        self._user_events: Dict[str, List[Dict]] = {}
        
        self.logger.info("📅 [CalendarManager] Inicializado")
    
    async def initialize(self) -> None:
        self.logger.info("📅 [CalendarManager] Inicializando...")
        self._running = True
        
        # Carrega eventos personalizados
        await self._load_events()
        
        # Calcula feriados móveis para o ano atual
        self._calculate_moveable_holidays()
        
        self.logger.info("📅 [CalendarManager] Inicializado")
    
    def _calculate_moveable_holidays(self) -> None:
        """Calcula feriados móveis (carnaval, páscoa, etc.)."""
        # Páscoa (algoritmo de computação)
        year = datetime.now().year
        
        # Algoritmo de Gauss para Páscoa
        a = year % 19
        b = year % 4
        c = year % 7
        d = (19 * a + 24) % 30
        e = (2 * b + 4 * c + 6 * d + 5) % 7
        
        if d + e < 10:
            easter_day = d + e + 22
            easter_month = 3
        else:
            easter_day = d + e - 9
            easter_month = 4
        
        easter = date(year, easter_month, easter_day)
        
        # Carnaval (47 dias antes da Páscoa)
        carnaval = easter - timedelta(days=47)
        
        # Sexta-feira Santa (2 dias antes da Páscoa)
        sexta_santa = easter - timedelta(days=2)
        
        # Corpus Christi (60 dias depois da Páscoa)
        corpus_christi = easter + timedelta(days=60)
        
        self._moveable_holidays = {
            carnaval.strftime("%m-%d"): "Carnaval",
            sexta_santa.strftime("%m-%d"): "Sexta-feira Santa",
            easter.strftime("%m-%d"): "Páscoa",
            corpus_christi.strftime("%m-%d"): "Corpus Christi"
        }
    
    def get_today_info(self) -> Dict[str, Any]:
        """Retorna informações do dia atual."""
        now = datetime.now()
        date_str = now.strftime("%m-%d")
        
        # Verifica feriados
        holiday = self._holidays.get(date_str)
        if not holiday:
            holiday = self._moveable_holidays.get(date_str)
        
        # Verifica eventos do usuário
        user_events = []
        # TODO: Buscar eventos do usuário atual
        
        return {
            "date": now.strftime("%d/%m/%Y"),
            "weekday": ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][now.weekday()],
            "is_weekend": now.weekday() >= 5,
            "holiday": holiday,
            "events": user_events
        }
    
    def get_month_calendar(self, year: int = None, month: int = None) -> Dict[str, Any]:
        """
        Retorna o calendário do mês.
        
        Args:
            year: Ano (opcional, padrão atual)
            month: Mês (opcional, padrão atual)
        """
        if not year or not month:
            now = datetime.now()
            year = year or now.year
            month = month or now.month
        
        # Dias do mês
        days_in_month = calendar.monthrange(year, month)[1]
        first_day = datetime(year, month, 1).weekday()
        
        days = []
        for day in range(1, days_in_month + 1):
            date_obj = date(year, month, day)
            date_str = date_obj.strftime("%m-%d")
            holiday = self._holidays.get(date_str) or self._moveable_holidays.get(date_str)
            
            days.append({
                "day": day,
                "weekday": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][date_obj.weekday()],
                "is_weekend": date_obj.weekday() >= 5,
                "holiday": holiday,
                "is_today": date_obj == date.today()
            })
        
        return {
            "year": year,
            "month": month,
            "month_name": ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                          "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"][month - 1],
            "days": days,
            "days_in_month": days_in_month,
            "first_day": first_day
        }
    
    async def add_event(self, user_id: str, date_str: str, title: str, 
                        description: str = "") -> bool:
        """Adiciona um evento personalizado."""
        try:
            if user_id not in self._user_events:
                self._user_events[user_id] = []
            
            self._user_events[user_id].append({
                "date": date_str,
                "title": title,
                "description": description,
                "created_at": datetime.now().isoformat()
            })
            
            await self._save_events()
            self.logger.info(f"📅 Evento adicionado: {title} em {date_str}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao adicionar evento: {e}")
            return False
    
    def get_user_events(self, user_id: str, date_str: str = None) -> List[Dict]:
        """Retorna eventos de um usuário."""
        events = self._user_events.get(user_id, [])
        
        if date_str:
            return [e for e in events if e.get("date") == date_str]
        
        return events
    
    async def _load_events(self) -> None:
        """Carrega eventos do disco."""
        try:
            data_path = Path(self.config.get("paths.data", "./data"))
            events_path = data_path / "calendar" / "events.json"
            
            if events_path.exists():
                with open(events_path, "r", encoding="utf-8") as f:
                    self._user_events = json.load(f)
        except Exception as e:
            self.logger.warning(f"Erro ao carregar eventos: {e}")
    
    async def _save_events(self) -> None:
        """Salva eventos no disco."""
        try:
            data_path = Path(self.config.get("paths.data", "./data"))
            events_path = data_path / "calendar" / "events.json"
            events_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(events_path, "w", encoding="utf-8") as f:
                json.dump(self._user_events, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Erro ao salvar eventos: {e}")
    
    async def shutdown(self) -> None:
        self.logger.info("📅 [CalendarManager] Desligando...")
        self._running = False
        await self._save_events()
        self.logger.info("📅 [CalendarManager] Desligado")
    
    async def health_check(self) -> dict:
        return {
            "status": "running" if self._running else "stopped",
            "holidays": len(self._holidays),
            "moveable_holidays": len(self._moveable_holidays),
            "user_events": len(self._user_events)
        }