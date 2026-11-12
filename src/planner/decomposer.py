"""Decompositor de objetivos em tarefas."""

from typing import List, Dict, Any, Optional
from datetime import datetime

from src.planner.goal import Goal, GoalType
from src.planner.task import Task, TaskPriority


class GoalDecomposer:
    """
    Decompõe objetivos em tarefas atômicas.
    """
    
    def __init__(self, planner_manager):
        self.planner_manager = planner_manager
        self.logger = planner_manager.logger
    
    async def decompose(self, goal: Goal) -> List[Task]:
        """
        Decompõe um objetivo em tarefas.
        
        Estratégias por tipo de objetivo:
        - ONESHOT: Tarefa única
        - RECURRING: Tarefa com agendamento
        - EMERGENCY: Tarefa de alta prioridade
        - LEARNING: Tarefas de estudo/pesquisa
        """
        if goal.goal_type == GoalType.ONESHOT:
            return await self._decompose_oneshot(goal)
        elif goal.goal_type == GoalType.RECURRING:
            return await self._decompose_recurring(goal)
        elif goal.goal_type == GoalType.EMERGENCY:
            return await self._decompose_emergency(goal)
        elif goal.goal_type == GoalType.LEARNING:
            return await self._decompose_learning(goal)
        elif goal.goal_type == GoalType.CONTINUOUS:
            return await self._decompose_continuous(goal)
        elif goal.goal_type == GoalType.MAINTENANCE:
            return await self._decompose_maintenance(goal)
        elif goal.goal_type == GoalType.EVOLUTION:
            return await self._decompose_evolution(goal)
        else:
            return await self._decompose_generic(goal)
    
    async def _decompose_oneshot(self, goal: Goal) -> List[Task]:
        """Decompõe objetivo único."""
        # Tenta identificar se há subtarefas no contexto
        subtasks = goal.context.get("subtasks", [])
        
        if subtasks:
            tasks = []
            for i, subtask in enumerate(subtasks):
                task = Task(
                    goal_id=goal.id,
                    name=subtask.get("name", f"Subtarefa {i+1}"),
                    description=subtask.get("description", ""),
                    priority=TaskPriority.NORMAL,
                    agent_name=subtask.get("agent"),
                    tool_name=subtask.get("tool"),
                    tool_params=subtask.get("params", {}),
                    dependencies=subtask.get("dependencies", []),
                    context=subtask.get("context", {})
                )
                tasks.append(task)
            return tasks
        
        # Tarefa única
        task = Task(
            goal_id=goal.id,
            name=goal.title,
            description=goal.description,
            priority=TaskPriority.NORMAL,
            context=goal.context.copy()
        )
        return [task]
    
    async def _decompose_recurring(self, goal: Goal) -> List[Task]:
        """Decompõe objetivo recorrente."""
        schedule = goal.context.get("schedule", {})
        
        task = Task(
            goal_id=goal.id,
            name=goal.title,
            description=goal.description,
            priority=TaskPriority.NORMAL,
            context={
                **goal.context,
                "schedule": schedule
            }
        )
        return [task]
    
    async def _decompose_emergency(self, goal: Goal) -> List[Task]:
        """Decompõe objetivo de emergência."""
        task = Task(
            goal_id=goal.id,
            name=f"URGENTE: {goal.title}",
            description=goal.description,
            priority=TaskPriority.CRITICAL,
            context=goal.context.copy()
        )
        return [task]
    
    async def _decompose_learning(self, goal: Goal) -> List[Task]:
        """Decompõe objetivo de aprendizado."""
        topics = goal.context.get("topics", [])
        tasks = []
        
        for topic in topics:
            task = Task(
                goal_id=goal.id,
                name=f"Aprender: {topic}",
                description=f"Estudar e aprender sobre {topic}",
                priority=TaskPriority.LOW,
                context={"topic": topic}
            )
            tasks.append(task)
        
        return tasks
    
    async def _decompose_continuous(self, goal: Goal) -> List[Task]:
        """Decompõe objetivo contínuo."""
        task = Task(
            goal_id=goal.id,
            name=f"Monitorar: {goal.title}",
            description=goal.description,
            priority=TaskPriority.BACKGROUND,
            context=goal.context.copy()
        )
        return [task]
    
    async def _decompose_maintenance(self, goal: Goal) -> List[Task]:
        """Decompõe objetivo de manutenção."""
        task = Task(
            goal_id=goal.id,
            name=f"Manutenção: {goal.title}",
            description=goal.description,
            priority=TaskPriority.LOW,
            context=goal.context.copy()
        )
        return [task]
    
    async def _decompose_evolution(self, goal: Goal) -> List[Task]:
        """Decompõe objetivo de evolução."""
        components = goal.context.get("components", [])
        
        if components:
            tasks = []
            for component in components:
                task = Task(
                    goal_id=goal.id,
                    name=f"Evoluir: {component}",
                    description=f"Atualizar e melhorar {component}",
                    priority=TaskPriority.LOW,
                    context={"component": component}
                )
                tasks.append(task)
            return tasks
        
        task = Task(
            goal_id=goal.id,
            name=f"Evoluir: {goal.title}",
            description=goal.description,
            priority=TaskPriority.LOW,
            context=goal.context.copy()
        )
        return [task]
    
    async def _decompose_generic(self, goal: Goal) -> List[Task]:
        """Decompõe objetivo genérico."""
        task = Task(
            goal_id=goal.id,
            name=goal.title,
            description=goal.description,
            priority=TaskPriority.NORMAL,
            context=goal.context.copy()
        )
        return [task]