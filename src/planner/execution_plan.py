"""Plano de execução do Planner."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import uuid4

from src.planner.goal import Goal
from src.planner.task import Task, TaskStatus


class PlanStatus(Enum):
    """Status de um plano."""
    DRAFT = "draft"
    APPROVED = "approved"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionPlan:
    """Plano completo de execução."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    goal_id: str = ""
    
    status: PlanStatus = PlanStatus.DRAFT
    
    # Hierarquia
    tasks: List[Task] = field(default_factory=list)
    
    # Ordem de execução (topológica)
    execution_order: List[str] = field(default_factory=list)
    
    # Timeline
    created_at: datetime = field(default_factory=datetime.now)
    approved_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Prioridade geral do plano
    priority: int = 5
    
    # Contexto do plano
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Resultado
    result: Optional[Dict[str, Any]] = None
    
    # Progresso (0.0 a 1.0)
    progress: float = 0.0
    
    def get_pending_tasks(self) -> List[Task]:
        """Obtém todas as tarefas pendentes."""
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]
    
    def get_ready_tasks(self) -> List[Task]:
        """Obtém tarefas prontas para execução."""
        ready = []
        for task in self.tasks:
            if not task.can_execute():
                continue
            
            # Verifica dependências
            deps_ok = True
            for dep_id in task.dependencies:
                dep = self._find_task(dep_id)
                if dep and not dep.is_done():
                    deps_ok = False
                    break
            
            if deps_ok:
                ready.append(task)
        
        return ready
    
    def _find_task(self, task_id: str) -> Optional[Task]:
        """Encontra uma task pelo ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def update_progress(self) -> float:
        """Atualiza e retorna o progresso do plano."""
        if not self.tasks:
            return 0.0
        
        done = sum(1 for t in self.tasks if t.is_done())
        in_progress = sum(1 for t in self.tasks if t.status == TaskStatus.IN_PROGRESS)
        
        # Peso: completas = 1, em progresso = 0.5
        self.progress = (done + (in_progress * 0.5)) / len(self.tasks)
        return self.progress
    
    def is_complete(self) -> bool:
        """Verifica se todas as tarefas foram concluídas."""
        return all(t.is_done() for t in self.tasks)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "goal_id": self.goal_id,
            "status": self.status.value,
            "task_count": len(self.tasks),
            "execution_order": self.execution_order,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "priority": self.priority,
            "progress": self.progress,
            "result": self.result
        }