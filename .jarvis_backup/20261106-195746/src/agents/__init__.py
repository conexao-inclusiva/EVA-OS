"""Módulo de Agentes da EVA OS."""

from src.agents.agent_manager import AgentManager
from src.agents.base_agent import BaseAgent
from src.agents.agent_registry import AgentRegistry

from src.agents.general_agent import GeneralAgent
from src.agents.knowledge_agent import KnowledgeAgent
from src.agents.memory_agent import MemoryAgent
from src.agents.planner_agent import PlannerAgent
from src.agents.home_automation_agent import HomeAutomationAgent
from src.agents.information_agent import InformationAgent
from src.agents.learning_agent import LearningAgent
from src.agents.security_agent import SecurityAgent

__all__ = [
    "AgentManager",
    "BaseAgent",
    "AgentRegistry",
    "GeneralAgent",
    "KnowledgeAgent",
    "MemoryAgent",
    "PlannerAgent",
    "HomeAutomationAgent",
    "InformationAgent",
    "LearningAgent",
    "SecurityAgent"
]