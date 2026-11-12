"""Rotas de planejamento da API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime

router = APIRouter()


class GoalRequest(BaseModel):
    """Requisição de objetivo."""
    title: str
    description: str
    priority: Optional[int] = 5


@router.post("/goal")
async def create_goal(request: GoalRequest):
    """Cria um objetivo."""
    # TODO: Implementar
    return {
        "status": "created",
        "goal_id": "TODO",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/plans")
async def list_plans():
    """Lista planos."""
    # TODO: Implementar
    return {
        "plans": [],
        "count": 0,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/plan/{plan_id}")
async def get_plan(plan_id: str):
    """Obtém um plano."""
    # TODO: Implementar
    return {
        "plan_id": plan_id,
        "found": False,
        "timestamp": datetime.now().isoformat()
    }