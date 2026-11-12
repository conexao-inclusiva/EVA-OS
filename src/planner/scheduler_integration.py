"""Integração com o Scheduler do Kernel."""

from typing import List, Optional
from datetime import datetime, timedelta

from src.kernel.scheduler import ScheduledTask, ScheduleType
from src.planner.task import Task, TaskStatus


class SchedulerIntegration:
    """
    Integra o Planner com o Scheduler do Kernel.
    Permite agendar tarefas para execução futura.
    """
    
    def __init__(self, planner_manager):
        self.planner_manager = planner_manager
        self.logger = planner_manager.logger
        self.scheduler = None  # Será injetado via service registry
    
    async def schedule_task(self, task: Task, scheduled_time: datetime) -> bool:
        """
        Agenda uma tarefa para execução futura.
        """
        if not self.scheduler:
            self.scheduler = self.planner_manager.event_bus.registry.get("scheduler")
            if not self.scheduler:
                self.logger.error("Scheduler não disponível")
                return False
        
        scheduled_task = ScheduledTask(
            name=task.name,
            description=task.description,
            schedule_type=ScheduleType.ONESHOT,
            func=self._execute_scheduled_task,
            args=[task.id],
            owner="planner"
        )
        
        # Define a próxima execução
        scheduled_task.next_run = scheduled_time
        
        self.scheduler.add_task(scheduled_task)
        
        self.logger.info(f"Tarefa {task.id[:8]} agendada para {scheduled_time}")
        return True
    
    async def schedule_recurring(self, task: Task, interval: float) -> bool:
        """
        Agenda uma tarefa recorrente.
        """
        if not self.scheduler:
            self.scheduler = self.planner_manager.event_bus.registry.get("scheduler")
            if not self.scheduler:
                self.logger.error("Scheduler não disponível")
                return False
        
        scheduled_task = ScheduledTask(
            name=f"Recorrente: {task.name}",
            description=task.description,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=interval,
            func=self._execute_scheduled_task,
            args=[task.id],
            owner="planner"
        )
        
        self.scheduler.add_task(scheduled_task)
        
        self.logger.info(f"Tarefa recorrente {task.id[:8]} agendada (intervalo: {interval}s)")
        return True
    
    async def _execute_scheduled_task(self, task_id: str) -> None:
        """
        Executa uma tarefa agendada.
        """
        self.logger.info(f"Executando tarefa agendada: {task_id}")
        
        # Encontra a tarefa em algum plano
        for plan in self.planner_manager._plans.values():
            for task in plan.tasks:
                if task.id == task_id:
                    task.status = TaskStatus.IN_PROGRESS
                    task.started_at = datetime.now()
                    
                    # Publica evento para execução
                    await self.planner_manager.event_bus.publish_async(
                        "task.execute",
                        {
                            "task": task.to_dict(),
                            "plan_id": plan.id
                        },
                        source="scheduler_integration"
                    )
                    return
        
        self.logger.warning(f"Tarefa não encontrada: {task_id}")