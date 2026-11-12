"""Tipos de eventos padronizados da EVA OS."""

from enum import Enum
from typing import Dict, Any, Optional


class EventType:
    """
    Tipos de eventos padronizados.
    
    Entrada:
    - USER_MESSAGE: Mensagem do usuário
    - SYSTEM_COMMAND: Comando do sistema
    
    Pipeline Cognitivo:
    - CONTEXT_READY: Contexto processado
    - MEMORY_RETRIEVED: Memórias recuperadas
    - KNOWLEDGE_QUERIED: Conhecimento consultado
    - PLAN_READY: Plano gerado
    - REASONING_READY: Raciocínio concluído
    - EMOTION_READY: Emoção analisada
    - PROMPT_READY: Prompt construído
    
    Saída (UNIFICADO):
    - ASSISTANT_RESPONSE: Resposta final
    
    Status:
    - PROCESSING_START: Início do processamento
    - PROCESSING_END: Fim do processamento
    
    Erros:
    - COGNITIVE_ERROR: Erro no pipeline
    - PIPELINE_FAILED: Falha no pipeline
    """
    
    # Entrada
    USER_MESSAGE = "user.message"
    SYSTEM_COMMAND = "system.command"
    
    # Pipeline Cognitivo
    CONTEXT_READY = "context.ready"
    MEMORY_RETRIEVED = "memory.retrieved"
    KNOWLEDGE_QUERIED = "knowledge.queried"
    PLAN_READY = "plan.ready"
    REASONING_READY = "reasoning.ready"
    EMOTION_READY = "emotion.ready"
    PROMPT_READY = "prompt.ready"
    
    # Saída (UNIFICADO)
    ASSISTANT_RESPONSE = "assistant.response"
    
    # Status
    PROCESSING_START = "processing.start"
    PROCESSING_END = "processing.end"
    
    # Erros
    COGNITIVE_ERROR = "cognitive.error"
    PIPELINE_FAILED = "pipeline.failed"


class EventPriority(Enum):
    """Prioridades de eventos."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


# Mapeamento de eventos para prioridades padrão
EVENT_PRIORITY_MAP = {
    EventType.USER_MESSAGE: EventPriority.NORMAL,
    EventType.SYSTEM_COMMAND: EventPriority.HIGH,
    EventType.CONTEXT_READY: EventPriority.NORMAL,
    EventType.MEMORY_RETRIEVED: EventPriority.NORMAL,
    EventType.KNOWLEDGE_QUERIED: EventPriority.NORMAL,
    EventType.PLAN_READY: EventPriority.NORMAL,
    EventType.REASONING_READY: EventPriority.NORMAL,
    EventType.EMOTION_READY: EventPriority.NORMAL,
    EventType.PROMPT_READY: EventPriority.NORMAL,
    EventType.ASSISTANT_RESPONSE: EventPriority.NORMAL,
    EventType.PROCESSING_START: EventPriority.LOW,
    EventType.PROCESSING_END: EventPriority.LOW,
    EventType.COGNITIVE_ERROR: EventPriority.HIGH,
    EventType.PIPELINE_FAILED: EventPriority.CRITICAL,
}