"""Módulo de Contexto da EVA OS."""

from src.context.context_manager import ContextManager
from src.context.conversation_context import ConversationContext, Message
from src.context.user_context import UserContext
from src.context.environment_context import EnvironmentContext
from src.context.system_context import SystemContext
from src.context.temporal_context import TemporalContext
from src.context.context_aggregator import ContextAggregator

__all__ = [
    "ContextManager",
    "ConversationContext",
    "Message",
    "UserContext",
    "EnvironmentContext",
    "SystemContext",
    "TemporalContext",
    "ContextAggregator"
]