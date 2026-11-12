"""Cálculo de prioridades do Planner."""

from datetime import datetime
from typing import Optional

from src.planner.goal import Goal, GoalStatus, GoalType
from src.planner.task import Task, TaskPriority


class PriorityCalculator:
    """
    Calcula prioridades para objetivos e tarefas.
    Baseado em urgência, importância e contexto.
    """
    
    @staticmethod
    def calculate_goal_priority(goal: Goal) -> int:
        """
        Calcula prioridade de um objetivo.
        Retorna: 0 (crítico) a 10 (baixo)
        """
        base_priority = goal.priority
        
        # Ajusta por status
        if goal.status == GoalStatus.BLOCKED:
            base_priority = min(base_priority + 2, 10)
        
        # Ajusta por deadline
        if goal.deadline:
            time_left = (goal.deadline - datetime.now()).total_seconds()
            if time_left < 3600:  # < 1 hora
                base_priority = max(base_priority - 3, 0)
            elif time_left < 86400:  # < 1 dia
                base_priority = max(base_priority - 1, 0)
        
        # Ajusta por tipo
        if goal.goal_type == GoalType.EMERGENCY:
            base_priority = 0
        elif goal.goal_type == GoalType.EVOLUTION:
            base_priority = min(base_priority + 2, 10)
        
        return max(0, min(10, base_priority))
    
    @staticmethod
    def calculate_task_priority(task: Task) -> TaskPriority:
        """
        Calcula prioridade de uma tarefa.
        """
        # Se tem deadline e está próximo
        if task.deadline:
            time_left = (task.deadline - datetime.now()).total_seconds()
            if time_left < 600:  # < 10 minutos
                return TaskPriority.CRITICAL
            elif time_left < 3600:  # < 1 hora
                return TaskPriority.HIGH
        
        # Se tem retry
        if task.retry_count > 0:
            return TaskPriority.HIGH
        
        return task.priority
    
    @staticmethod
    def sort_tasks_by_priority(tasks: list) -> list:
        """Ordena tarefas por prioridade (maior prioridade primeiro)."""
        def priority_key(task):
            return PriorityCalculator.calculate_task_priority(task).value
        
        return sorted(tasks, key=priority_key)
    
    @staticmethod
    def get_priority_score(priority: TaskPriority) -> int:
        """Converte enum para score numérico."""
        return priority.value