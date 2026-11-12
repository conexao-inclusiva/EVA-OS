"""Gerenciador de Lembretes da EVA."""

import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field

from src.kernel.events import EventBus
from src.core.event_types import EventType


@dataclass
class Reminder:
    """Estrutura de um lembrete."""
    id: str
    user_id: str
    title: str
    description: str
    datetime: str
    recurring: bool = False
    recurring_type: str = "daily"  # daily, weekly, monthly
    completed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notified: bool = False


class ReminderManager:
    """
    Gerenciador de Lembretes da EVA.
    
    Responsabilidades:
    - Criar lembretes
    - Listar lembretes ativos
    - Notificar lembretes vencidos
    - Concluir lembretes
    """
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        self._reminders: Dict[str, Reminder] = {}
        self._running = False
        self._check_task: Optional[asyncio.Task] = None
        
        data_path = Path(config.get("paths.data", "./data"))
        self._reminders_path = data_path / "reminders" / "reminders.json"
        self._reminders_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("⏰ [ReminderManager] Inicializado")
    
    async def initialize(self) -> None:
        self.logger.info("⏰ [ReminderManager] Inicializando...")
        self._running = True
        
        await self._load_reminders()
        
        # Inicia verificação periódica
        self._check_task = asyncio.create_task(self._check_reminders())
        
        self.logger.info(f"⏰ [ReminderManager] {len(self._reminders)} lembretes carregados")
    
    async def add_reminder(self, user_id: str, title: str, description: str,
                          datetime_str: str, recurring: bool = False,
                          recurring_type: str = "daily") -> Dict[str, Any]:
        """Adiciona um novo lembrete."""
        import uuid
        
        reminder = Reminder(
            id=str(uuid.uuid4())[:8],
            user_id=user_id,
            title=title,
            description=description,
            datetime=datetime_str,
            recurring=recurring,
            recurring_type=recurring_type
        )
        
        self._reminders[reminder.id] = reminder
        await self._save_reminders()
        
        self.logger.info(f"⏰ [ReminderManager] Lembrete criado: {title}")
        
        return {
            "id": reminder.id,
            "title": title,
            "datetime": datetime_str,
            "status": "criado"
        }
    
    async def get_reminders(self, user_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Lista lembretes de um usuário."""
        result = []
        for reminder in self._reminders.values():
            if reminder.user_id != user_id:
                continue
            if active_only and reminder.completed:
                continue
            result.append({
                "id": reminder.id,
                "title": reminder.title,
                "description": reminder.description,
                "datetime": reminder.datetime,
                "recurring": reminder.recurring,
                "recurring_type": reminder.recurring_type,
                "completed": reminder.completed,
                "notified": reminder.notified
            })
        
        # Ordena por data
        result.sort(key=lambda x: x["datetime"])
        return result
    
    async def complete_reminder(self, reminder_id: str) -> bool:
        """Marca um lembrete como concluído."""
        reminder = self._reminders.get(reminder_id)
        if not reminder:
            return False
        
        reminder.completed = True
        await self._save_reminders()
        self.logger.info(f"⏰ [ReminderManager] Lembrete concluído: {reminder.title}")
        return True
    
    async def _check_reminders(self) -> None:
        """Verifica lembretes vencidos periodicamente."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Verifica a cada 30 segundos
                
                now = datetime.now()
                for reminder in self._reminders.values():
                    if reminder.completed or reminder.notified:
                        continue
                    
                    reminder_time = datetime.fromisoformat(reminder.datetime)
                    if reminder_time <= now:
                        # Notifica
                        await self._notify_reminder(reminder)
                        reminder.notified = True
                        
                        # Se for recorrente, agenda próximo
                        if reminder.recurring:
                            next_time = self._get_next_recurrence(reminder_time, reminder.recurring_type)
                            reminder.datetime = next_time.isoformat()
                            reminder.notified = False
                            self.logger.info(f"⏰ [ReminderManager] Próximo lembrete: {reminder.title} em {next_time}")
                        
                        await self._save_reminders()
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Erro ao verificar lembretes: {e}")
    
    def _get_next_recurrence(self, current_time: datetime, recurring_type: str) -> datetime:
        """Calcula a próxima recorrência."""
        if recurring_type == "daily":
            return current_time + timedelta(days=1)
        elif recurring_type == "weekly":
            return current_time + timedelta(days=7)
        elif recurring_type == "monthly":
            return current_time + timedelta(days=30)
        return current_time + timedelta(days=1)
    
    async def _notify_reminder(self, reminder: Reminder) -> None:
        """Notifica um lembrete."""
        self.logger.info(f"⏰ [ReminderManager] 🔔 LEMBRETE: {reminder.title}")
        
        # Publica evento para notificação
        await self.event_bus.publish_async(
            "reminder.notification",
            {
                "user_id": reminder.user_id,
                "title": reminder.title,
                "description": reminder.description,
                "datetime": reminder.datetime,
                "id": reminder.id
            },
            source="reminder_manager"
        )
    
    async def _load_reminders(self) -> None:
        """Carrega lembretes do disco."""
        try:
            if self._reminders_path.exists():
                with open(self._reminders_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        reminder = Reminder(**item)
                        self._reminders[reminder.id] = reminder
        except Exception as e:
            self.logger.warning(f"Erro ao carregar lembretes: {e}")
    
    async def _save_reminders(self) -> None:
        """Salva lembretes no disco."""
        try:
            data = []
            for reminder in self._reminders.values():
                data.append({
                    "id": reminder.id,
                    "user_id": reminder.user_id,
                    "title": reminder.title,
                    "description": reminder.description,
                    "datetime": reminder.datetime,
                    "recurring": reminder.recurring,
                    "recurring_type": reminder.recurring_type,
                    "completed": reminder.completed,
                    "created_at": reminder.created_at,
                    "notified": reminder.notified
                })
            with open(self._reminders_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Erro ao salvar lembretes: {e}")
    
    async def shutdown(self) -> None:
        self.logger.info("⏰ [ReminderManager] Desligando...")
        self._running = False
        if self._check_task:
            self._check_task.cancel()
        await self._save_reminders()
        self.logger.info("⏰ [ReminderManager] Desligado")
    
    async def health_check(self) -> dict:
        active = sum(1 for r in self._reminders.values() if not r.completed)
        return {
            "status": "running" if self._running else "stopped",
            "total_reminders": len(self._reminders),
            "active_reminders": active
        }