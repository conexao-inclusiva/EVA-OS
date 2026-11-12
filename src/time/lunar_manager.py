"""Gerenciador de Fases da Lua da EVA."""

import math
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json
from pathlib import Path

from src.kernel.events import EventBus


class LunarManager:
    """
    Gerenciador de Fases da Lua da EVA.
    
    Responsabilidades:
    - Calcular a fase atual da lua
    - Nascer e pôr da lua (aproximado)
    - Próximas fases
    - Informações lunares
    """
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        self._running = False
        
        # Nomes das fases em português
        self._phases_pt = {
            "new_moon": "Lua Nova",
            "waxing_crescent": "Lua Crescente",
            "first_quarter": "Quarto Crescente",
            "waxing_gibbous": "Lua Gibosa Crescente",
            "full_moon": "Lua Cheia",
            "waning_gibbous": "Lua Gibosa Minguante",
            "last_quarter": "Quarto Minguante",
            "waning_crescent": "Lua Minguante"
        }
        
        # Emojis para cada fase
        self._phase_emojis = {
            "new_moon": "🌑",
            "waxing_crescent": "🌒",
            "first_quarter": "🌓",
            "waxing_gibbous": "🌔",
            "full_moon": "🌕",
            "waning_gibbous": "🌖",
            "last_quarter": "🌗",
            "waning_crescent": "🌘"
        }
        
        self.logger.info("🌙 [LunarManager] Inicializado")
    
    async def initialize(self) -> None:
        self.logger.info("🌙 [LunarManager] Inicializando...")
        self._running = True
        self.logger.info("🌙 [LunarManager] Inicializado")
    
    def get_moon_phase(self, date: datetime = None) -> Dict[str, Any]:
        """
        Calcula a fase da lua para uma data específica.
        
        Args:
            date: Data (opcional, padrão atual)
            
        Returns:
            Dicionário com informações da fase lunar
        """
        if not date:
            date = datetime.now()
        
        # Algoritmo para calcular a fase da lua
        # Baseado no ciclo lunar de 29.53 dias
        
        # Data de referência: Lua Nova em 1 de janeiro de 2000
        reference = datetime(2000, 1, 6, 18, 14)  # Lua Nova conhecida
        
        # Dias desde a referência
        days_diff = (date - reference).total_seconds() / 86400
        
        # Ciclo lunar (29.53058867 dias)
        lunar_cycle = 29.53058867
        
        # Fase atual (0 a 1)
        phase = (days_diff % lunar_cycle) / lunar_cycle
        
        # Determina a fase
        if phase < 0.0625:
            phase_name = "new_moon"
            phase_label = "Lua Nova"
            emoji = "🌑"
        elif phase < 0.1875:
            phase_name = "waxing_crescent"
            phase_label = "Lua Crescente"
            emoji = "🌒"
        elif phase < 0.3125:
            phase_name = "first_quarter"
            phase_label = "Quarto Crescente"
            emoji = "🌓"
        elif phase < 0.4375:
            phase_name = "waxing_gibbous"
            phase_label = "Lua Gibosa Crescente"
            emoji = "🌔"
        elif phase < 0.5625:
            phase_name = "full_moon"
            phase_label = "Lua Cheia"
            emoji = "🌕"
        elif phase < 0.6875:
            phase_name = "waning_gibbous"
            phase_label = "Lua Gibosa Minguante"
            emoji = "🌖"
        elif phase < 0.8125:
            phase_name = "last_quarter"
            phase_label = "Quarto Minguante"
            emoji = "🌗"
        else:
            phase_name = "waning_crescent"
            phase_label = "Lua Minguante"
            emoji = "🌘"
        
        # Próximas fases (aproximadas)
        next_phases = self._get_next_phases(date)
        
        return {
            "phase": phase_name,
            "phase_label": phase_label,
            "emoji": emoji,
            "age_days": round(phase * lunar_cycle, 1),
            "illumination": round((1 - math.cos(phase * 2 * math.pi)) / 2 * 100, 1),
            "next_phases": next_phases,
            "date": date.strftime("%d/%m/%Y")
        }
    
    def _get_next_phases(self, date: datetime) -> List[Dict[str, Any]]:
        """Calcula as próximas fases da lua."""
        phases = []
        reference = datetime(2000, 1, 6, 18, 14)
        lunar_cycle = 29.53058867
        
        days_diff = (date - reference).total_seconds() / 86400
        current_phase = days_diff % lunar_cycle
        
        # Próximas 4 fases
        phase_dates = [
            ("Lua Nova", 0),
            ("Quarto Crescente", lunar_cycle / 4),
            ("Lua Cheia", lunar_cycle / 2),
            ("Quarto Minguante", lunar_cycle * 3 / 4)
        ]
        
        for name, offset in phase_dates:
            days_until = offset - current_phase
            if days_until < 0:
                days_until += lunar_cycle
            
            next_date = date + timedelta(days=days_until)
            phases.append({
                "name": name,
                "date": next_date.strftime("%d/%m/%Y"),
                "days_until": round(days_until, 1)
            })
        
        return phases
    
    def get_moon_emoji(self, date: datetime = None) -> str:
        """Retorna o emoji da fase atual da lua."""
        info = self.get_moon_phase(date)
        return info.get("emoji", "🌙")
    
    def get_moon_phase_description(self, date: datetime = None) -> str:
        """Retorna uma descrição da fase atual da lua."""
        info = self.get_moon_phase(date)
        phase = info.get("phase_label", "desconhecida")
        emoji = info.get("emoji", "")
        illumination = info.get("illumination", 0)
        
        return f"{emoji} {phase} (iluminada em {illumination:.0f}%)"
    
    async def shutdown(self) -> None:
        self.logger.info("🌙 [LunarManager] Desligando...")
        self._running = False
        self.logger.info("🌙 [LunarManager] Desligado")
    
    async def health_check(self) -> dict:
        return {
            "status": "running" if self._running else "stopped"
        }