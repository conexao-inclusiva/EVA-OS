"""Definição de tarefas do Planner."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Callable
from uuid import uuid4


class TaskStatus(Enum):
    """Status de uma tarefa."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class TaskPriority(Enum):
    """Prioridade de tarefa."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class Task:
    """Uma tarefa atômica executável."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    goal_id: str = ""  # Goal pai
    name: str = ""
    description: str = ""
    
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    
    # Agente que deve executar
    agent_name: Optional[str] = None
    
    # Ferramenta a ser usada
    tool_name: Optional[str] = None
    tool_params: Dict[str, Any] = field(default_factory=dict)
    
    # Dependências
    dependencies: List[str] = field(default_factory=list)  # IDs de tasks
    depends_on_goals: List[str] = field(default_factory=list)  # IDs de goals
    
    # Timeline
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    estimated_duration: Optional[float] = None  # segundos
    
    # Quem criou
    created_by: str = "system"
    assigned_to: Optional[str] = None
    
    # Retry
    max_retries: int = 3
    retry_count: int = 0
    retry_delay: float = 5.0
    
    # Resultado
    result: Optional[Any] = None
    error: Optional[str] = None
    
    # Callbacks
    on_complete: Optional[Callable] = None
    on_error: Optional[Callable] = None
    
    # Contexto
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Progresso (0.0 a 1.0)
    progress: float = 0.0
    
    def can_execute(self) -> bool:
        """Verifica se a tarefa pode ser executada."""
        if self.status not in [TaskStatus.PENDING, TaskStatus.SCHEDULED]:
            return False
        if self.scheduled_at and self.scheduled_at > datetime.now():
            return False
        return True
    
    def is_done(self) -> bool:
        return self.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED]
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "goal_id": self.goal_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "agent_name": self.agent_name,
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "dependencies": self.dependencies,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "result": self.result,
            "error": self.error,
            "progress": self.progress
        }