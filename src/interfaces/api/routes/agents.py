"""Rotas de agentes da API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime

router = APIRouter()


@router.get("/")
async def list_agents():
    """Lista agentes."""
    # TODO: Implementar
    return {
        "agents": [
            {"name": "general", "status": "idle"},
            {"name": "knowledge", "status": "idle"},
            {"name": "memory", "status": "idle"},
            {"name": "planner", "status": "idle"},
            {"name": "home_automation", "status": "idle"},
            {"name": "information", "status": "idle"},
            {"name": "learning", "status": "idle"},
            {"name": "security", "status": "idle"}
        ],
        "count": 8,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/{agent_name}")
async def get_agent(agent_name: str):
    """Obtém informações de um agente."""
    # TODO: Implementar
    return {
        "agent": agent_name,
        "found": True,
        "status": "idle",
        "capabilities": ["general", "conversation"],
        "timestamp": datetime.now().isoformat()
    }