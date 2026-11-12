"""Agendador de tarefas do Kernel."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from uuid import uuid4


class ScheduleType(Enum):
    """Tipo de agendamento."""
    ONESHOT = auto()        # Única execução
    INTERVAL = auto()       # Intervalo fixo
    CRON = auto()           # Cron-like
    DAILY = auto()          # Diário
    WEEKLY = auto()         # Semanal
    MONTHLY = auto()        # Mensal
    STARTUP = auto()        # Na inicialização
    SHUTDOWN = auto()       # No desligamento


@dataclass
class ScheduledTask:
    """Tarefa agendada."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    
    schedule_type: ScheduleType = ScheduleType.ONESHOT
    
    # Para interval
    interval_seconds: float = 60.0
    
    # Para cron/daily/weekly/monthly
    cron_expression: Optional[str] = None
    time_of_day: Optional[str] = None  # HH:MM
    day_of_week: Optional[int] = None  # 0-6
    day_of_month: Optional[int] = None  # 1-31
    
    # Execução
    func: Optional[Callable] = None
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    is_async: bool = False
    
    # Controle
    enabled: bool = True
    run_on_startup: bool = False
    run_on_shutdown: bool = False
    
    # Estatísticas
    created_at: datetime = field(default_factory=datetime.now)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    
    # Retry
    max_retries: int = 3
    retry_delay: float = 5.0
    
    # Owner
    owner: str = "system"


class Scheduler:
    """
    Agendador de tarefas do Kernel.
    Tudo agendado passa aqui.
    Backup, pesquisa, treinamento, lembretes, estudo autônomo...
    """
    
    def __init__(self, logger, event_bus):
        self.logger = logger
        self.event_bus = event_bus
        
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._check_interval = 1.0  # segundos
        
        # Detector de inatividade
        self._last_user_activity = datetime.now()
        self._idle_threshold = 300 # 5 minutos
        
        # Ouve eventos para detectar atividade
        self.event_bus.subscribe("user.message", self._on_activity)
    
    def _on_activity(self, event: Any) -> None:
        """Atualiza marca de tempo de atividade."""
        self._last_user_activity = datetime.now()
    
    async def initialize(self) -> None:
        """Inicializa o scheduler."""
        self._running = True
        self._worker_task = asyncio.create_task(self._run_scheduler())
        self.logger.info("Scheduler inicializado com detecção de ociosidade")
    
    def add_task(self, task: ScheduledTask) -> str:
        """Adiciona uma tarefa ao scheduler."""
        # Calcula próxima execução
        task.next_run = self._calculate_next_run(task)
        
        self._tasks[task.id] = task
        self.logger.info(f"Tarefa agendada: {task.name} (ID: {task.id[:8]})")
        
        # Publica evento
        asyncio.create_task(self._publish_task_added(task))
        
        return task.id
    
    def remove_task(self, task_id: str) -> bool:
        """Remove uma tarefa."""
        if task_id in self._tasks:
            task = self._tasks.pop(task_id)
            self.logger.info(f"Tarefa removida: {task.name}")
            return True
        return False
    
    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Obtém uma tarefa pelo ID."""
        return self._tasks.get(task_id)
    
    def get_tasks(self, owner: Optional[str] = None) -> List[ScheduledTask]:
        """Lista tarefas, opcionalmente filtrando por owner."""
        if owner:
            return [t for t in self._tasks.values() if t.owner == owner]
        return list(self._tasks.values())
    
    def enable_task(self, task_id: str) -> bool:
        """Habilita uma tarefa."""
        task = self._tasks.get(task_id)
        if task:
            task.enabled = True
            task.next_run = self._calculate_next_run(task)
            self.logger.info(f"Tarefa habilitada: {task.name}")
            return True
        return False
    
    def disable_task(self, task_id: str) -> bool:
        """Desabilita uma tarefa."""
        task = self._tasks.get(task_id)
        if task:
            task.enabled = False
            self.logger.info(f"Tarefa desabilitada: {task.name}")
            return True
        return False
    
    def _calculate_next_run(self, task: ScheduledTask) -> Optional[datetime]:
        """Calcula a próxima execução da tarefa."""
        now = datetime.now()
        
        if not task.enabled:
            return None
        
        if task.schedule_type == ScheduleType.ONESHOT:
            return now
        
        elif task.schedule_type == ScheduleType.STARTUP:
            return now
        
        elif task.schedule_type == ScheduleType.SHUTDOWN:
            return None
        
        elif task.schedule_type == ScheduleType.INTERVAL:
            if task.last_run:
                return task.last_run + timedelta(seconds=task.interval_seconds)
            return now + timedelta(seconds=task.interval_seconds)
        
        elif task.schedule_type == ScheduleType.DAILY:
            if task.time_of_day:
                hour, minute = map(int, task.time_of_day.split(":"))
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                return next_run
            return now + timedelta(days=1)
        
        elif task.schedule_type == ScheduleType.WEEKLY:
            if task.day_of_week is not None and task.time_of_day:
                hour, minute = map(int, task.time_of_day.split(":"))
                days_ahead = task.day_of_week - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                next_run = now + timedelta(days=days_ahead)
                next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return next_run
            return now + timedelta(days=7)
        
        elif task.schedule_type == ScheduleType.MONTHLY:
            if task.day_of_month is not None:
                day = min(task.day_of_month, 28)
                next_run = now.replace(day=day, hour=0, minute=0, second=0, microsecond=0)
                if next_run <= now:
                    if now.month == 12:
                        next_run = next_run.replace(year=now.year + 1, month=1)
                    else:
                        next_run = next_run.replace(month=now.month + 1)
                return next_run
            return now + timedelta(days=30)
        
        return None
    
    async def _run_scheduler(self) -> None:
        """Loop principal do scheduler."""
        while self._running:
            try:
                now = datetime.now()
                
                # Check ociosidade
                if (now - self._last_user_activity).total_seconds() > self._idle_threshold:
                    await self.event_bus.publish_async("system.idle", {}, source="scheduler")
                    # Delay para evitar spam de eventos de idle
                    self._last_user_activity = now + timedelta(minutes=1)
                
                for task in self._tasks.values():
                    if not task.enabled:
                        continue
                    
                    if task.next_run and task.next_run <= now:
                        asyncio.create_task(self._execute_task(task))
                        task.last_run = now
                        task.next_run = self._calculate_next_run(task)
                
                await asyncio.sleep(self._check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Erro no scheduler: {e}")
                await asyncio.sleep(5)
    
    async def _execute_task(self, task: ScheduledTask) -> None:
        """Executa uma tarefa."""
        if not task.func:
            return
        
        self.logger.debug(f"Executando tarefa: {task.name}")
        
        try:
            if task.is_async:
                await task.func(*task.args, **task.kwargs)
            else:
                if asyncio.iscoroutinefunction(task.func):
                    await task.func(*task.args, **task.kwargs)
                else:
                    task.func(*task.args, **task.kwargs)
            
            task.run_count += 1
            task.last_error = None
            await self._publish_task_executed(task, success=True)
            
        except Exception as e:
            task.error_count += 1
            task.last_error = str(e)
            self.logger.error(f"Erro na tarefa {task.name}: {e}")
            
            if task.error_count <= task.max_retries:
                await asyncio.sleep(task.retry_delay)
                asyncio.create_task(self._execute_task(task))
            else:
                task.enabled = False
            
            await self._publish_task_executed(task, success=False, error=str(e))
    
    async def _publish_task_added(self, task: ScheduledTask) -> None:
        """Publica evento de tarefa adicionada."""
        await self.event_bus.publish_async(
            "SCHEDULER_TASK_ADDED",
            {
                "task_id": task.id,
                "name": task.name,
                "schedule_type": task.schedule_type.name,
                "next_run": task.next_run.isoformat() if task.next_run else None,
                "owner": task.owner
            },
            source="scheduler"
        )
    
    async def _publish_task_executed(self, task: ScheduledTask, success: bool, error: str = None) -> None:
        """Publica evento de tarefa executada."""
        await self.event_bus.publish_async(
            "SCHEDULER_TASK_EXECUTED",
            {
                "task_id": task.id,
                "name": task.name,
                "success": success,
                "error": error,
                "run_count": task.run_count,
                "timestamp": datetime.now().isoformat()
            },
            source="scheduler"
        )
    
    def run_startup_tasks(self) -> None:
        """Executa tarefas marcadas para startup."""
        for task in self._tasks.values():
            if task.run_on_startup and task.enabled:
                asyncio.create_task(self._execute_task(task))
    
    async def run_shutdown_tasks(self) -> None:
        """Executa tarefas marcadas para shutdown."""
        for task in self._tasks.values():
            if task.run_on_shutdown and task.enabled:
                await self._execute_task(task)
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas do scheduler."""
        return {
            "total_tasks": len(self._tasks),
            "enabled_tasks": sum(1 for t in self._tasks.values() if t.enabled),
            "running": self._running
        }
    
    async def shutdown(self) -> None:
        """Desliga o scheduler."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Scheduler desligado")
