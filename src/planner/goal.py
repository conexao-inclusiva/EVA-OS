"""Definição de objetivos do Planner."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import uuid4


class GoalStatus(Enum):
    """Status de um objetivo."""
    DRAFT = "draft"
    APPROVED = "approved"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class GoalType(Enum):
    """Tipo de objetivo."""
    ONESHOT = "oneshot"          # Única execução
    RECURRING = "recurring"      # Recorrente
    CONTINUOUS = "continuous"    # Contínuo (monitoramento)
    EMERGENCY = "emergency"      # Emergência
    MAINTENANCE = "maintenance"  # Manutenção
    LEARNING = "learning"        # Aprendizado
    EVOLUTION = "evolution"      # Auto-evolução


@dataclass
class Goal:
    """Um objetivo que o Planner deve realizar."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    description: str = ""
    goal_type: GoalType = GoalType.ONESHOT
    status: GoalStatus = GoalStatus.DRAFT
    
    # Prioridade: 0 (crítico) a 10 (baixo)
    priority: int = 5
    
    # Quem criou
    created_by: str = "system"
    created_at: datetime = field(default_factory=datetime.now)
    
    # Metadados
    deadline: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # IDs de outros goals
    parent_goal: Optional[str] = None
    
    # Contexto
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Resultado
    result: Optional[Dict[str, Any]] = None
    completed_at: Optional[datetime] = None
    
    # Progresso (0.0 a 1.0)
    progress: float = 0.0
    
    def is_complete(self) -> bool:
        return self.status == GoalStatus.COMPLETED
    
    def is_active(self) -> bool:
        return self.status in [GoalStatus.APPROVED, GoalStatus.PLANNING, GoalStatus.IN_PROGRESS]
    
    def can_start(self) -> bool:
        return self.status == GoalStatus.APPROVED and self.progress == 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "goal_type": self.goal_type.value,
            "status": self.status.value,
            "priority": self.priority,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "parent_goal": self.parent_goal,
            "progress": self.progress,
            "result": self.result
        }