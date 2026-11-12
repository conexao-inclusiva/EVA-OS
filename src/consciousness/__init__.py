"""Módulo de Consciência da EVA OS."""

from src.consciousness.consciousness_manager import ConsciousnessManager, ConsciousnessState
from src.consciousness.decision_engine import DecisionEngine, Decision, DecisionType
from src.consciousness.intent_classifier import IntentClassifier
from src.consciousness.intent_router import IntentRouter
from src.consciousness.context_analyzer import ContextAnalyzer
from src.consciousness.priority_arbiter import PriorityArbiter
from src.consciousness.reflection_engine import ReflectionEngine
from src.consciousness.state_orchestrator import StateOrchestrator

__all__ = [
    "ConsciousnessManager",
    "ConsciousnessState",
    "DecisionEngine",
    "Decision",
    "DecisionType",
    "IntentClassifier",
    "IntentRouter",
    "ContextAnalyzer",
    "PriorityArbiter",
    "ReflectionEngine",
    "StateOrchestrator"
]