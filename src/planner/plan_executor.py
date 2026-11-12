"""Executor de planos."""

from typing import List, Optional
from datetime import datetime

from src.planner.execution_plan import ExecutionPlan, PlanStatus
from src.planner.task import Task, TaskStatus


class PlanExecutor:
    """
    Executa planos de forma coordenada.
    """
    
    def __init__(self, planner_manager):
        self.planner_manager = planner_manager
        self.logger = planner_manager.logger
        
        # Controle de execução
        self._executing_plans: dict = {}  # plan_id -> set de task_ids em execução
        self._paused_plans: set = set()
    
    async def execute(self, plan: ExecutionPlan) -> bool:
        """
        Inicia a execução de um plano.
        """
        if plan.status == PlanStatus.EXECUTING:
            return False
        
        # Inicializa controle
        self._executing_plans[plan.id] = set()
        plan.status = PlanStatus.EXECUTING
        plan.started_at = datetime.now()
        
        # Inicia tarefas prontas
        await self._execute_ready_tasks(plan)
        
        return True
    
    async def pause(self, plan: ExecutionPlan) -> bool:
        """
        Pausa a execução de um plano.
        """
        if plan.status != PlanStatus.EXECUTING:
            return False
        
        self._paused_plans.add(plan.id)
        plan.status = PlanStatus.PAUSED
        
        # Pausa tarefas em execução (serão retomadas)
        self.logger.info(f"Plano pausado: {plan.id[:8]}")
        return True
    
    async def resume(self, plan: ExecutionPlan) -> bool:
        """
        Retoma a execução de um plano.
        """
        if plan.status != PlanStatus.PAUSED:
            return False
        
        self._paused_plans.discard(plan.id)
        plan.status = PlanStatus.EXECUTING
        
        # Continua execução
        await self._execute_ready_tasks(plan)
        
        self.logger.info(f"Plano retomado: {plan.id[:8]}")
        return True
    
    async def cancel(self, plan: ExecutionPlan) -> bool:
        """
        Cancela a execução de um plano.
        """
        if plan.id in self._executing_plans:
            del self._executing_plans[plan.id]
        
        self._paused_plans.discard(plan.id)
        plan.status = PlanStatus.CANCELLED
        
        # Cancela tarefas pendentes
        for task in plan.tasks:
            if task.status in [TaskStatus.PENDING, TaskStatus.SCHEDULED]:
                task.status = TaskStatus.CANCELLED
        
        self.logger.info(f"Plano cancelado: {plan.id[:8]}")
        return True
    
    async def continue_execution(self, plan: ExecutionPlan) -> None:
        """
        Continua a execução de um plano após uma tarefa ser concluída.
        """
        if plan.id in self._paused_plans:
            return
        
        if plan.status != PlanStatus.EXECUTING:
            return
        
        await self._execute_ready_tasks(plan)
    
    async def retry_task(self, plan: ExecutionPlan, task: Task) -> None:
        """
        Tenta executar uma tarefa novamente.
        """
        self.logger.info(f"Tentando novamente task {task.id[:8]} (tentativa {task.retry_count})")
        
        # Aguarda o delay
        import asyncio
        await asyncio.sleep(task.retry_delay)
        
        # Reagenda
        task.status = TaskStatus.PENDING
        await self._execute_task(plan, task)
    
    async def _execute_ready_tasks(self, plan: ExecutionPlan) -> None:
        """
        Executa todas as tarefas prontas do plano.
        """
        if plan.id in self._paused_plans:
            return
        
        ready_tasks = plan.get_ready_tasks()
        
        if not ready_tasks:
            # Verifica se há tarefas em andamento
            active = self._executing_plans.get(plan.id, set())
            if not active:
                # Nenhuma tarefa em andamento e nenhuma pronta
                # Verifica se o plano está completo
                if plan.is_complete():
                    plan.status = PlanStatus.COMPLETED
                    plan.completed_at = datetime.now()
                    self.logger.info(f"Plano concluído: {plan.id[:8]}")
                else:
                    # Pode haver deadlock ou erro
                    self.logger.warning(f"Plano {plan.id[:8]} sem tarefas prontas e não completo")
            return
        
        # Ordena por prioridade
        from src.planner.priority import PriorityCalculator
        ready_tasks = PriorityCalculator.sort_tasks_by_priority(ready_tasks)
        
        for task in ready_tasks:
            await self._execute_task(plan, task)
    
    async def _execute_task(self, plan: ExecutionPlan, task: Task) -> None:
        """
        Executa uma tarefa específica.
        """
        if task.status != TaskStatus.PENDING:
            return
        
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()
        
        # Registra em execução
        if plan.id not in self._executing_plans:
            self._executing_plans[plan.id] = set()
        self._executing_plans[plan.id].add(task.id)
        
        self.logger.debug(f"Executando task: {task.name} ({task.id[:8]})")
        
        # Publica evento para execução
        await self.planner_manager.event_bus.publish_async(
            "task.execute",
            {
                "task": task.to_dict(),
                "plan_id": plan.id
            },
            source="plan_executor"
        )