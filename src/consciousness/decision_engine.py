"""Motor de decisão da Consciência."""

from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class DecisionType(Enum):
    """Tipos de decisão."""
    ROUTE_TO_AGENT = "route_to_agent"
    CREATE_PLAN = "create_plan"
    EXECUTE_TOOL = "execute_tool"
    RESPOND = "respond"
    ASK_CLARIFICATION = "ask_clarification"
    DEFER = "defer"
    EMERGENCY = "emergency"
    REFLECT = "reflect"


class Decision:
    """Uma decisão tomada pela Consciência."""
    
    def __init__(self, decision_type: DecisionType, target: str = "",
                 confidence: float = 0.5, reason: str = "",
                 data: Dict[str, Any] = None):
        self.type = decision_type
        self.target = target
        self.confidence = confidence
        self.reason = reason
        self.data = data or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "type": self.type.value,
            "target": self.target,
            "confidence": self.confidence,
            "reason": self.reason,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }


class DecisionEngine:
    """
    Motor de decisão da Consciência.
    
    Responsabilidades:
    - Receber intenções e contexto
    - Avaliar opções
    - Tomar decisões
    - Justificar decisões
    """
    
    def __init__(self, consciousness_manager):
        self.consciousness = consciousness_manager
        self.logger = consciousness_manager.logger
        self.event_bus = consciousness_manager.event_bus
    
    async def decide(self, intent: Dict[str, Any], context: Dict[str, Any], 
                     event: Optional[Any] = None) -> Decision:
        """
        Toma uma decisão baseada na intenção e contexto.
        """
        intent_type = intent.get("type", "unknown")
        confidence = intent.get("confidence", 0.5)
        
        self.logger.debug(f"Decidindo para intenção: {intent_type}")
        
        # 1. Emergência - prioridade máxima
        if intent_type == "emergency":
            return await self._decide_emergency(intent, context)
        
        # 2. Comando direto
        if intent_type == "command":
            return await self._decide_command(intent, context)
        
        # 3. Pergunta
        if intent_type == "question":
            return await self._decide_question(intent, context)
        
        # 4. Planejamento
        if intent_type == "planning":
            return await self._decide_planning(intent, context)
        
        # 5. Conversa
        if intent_type == "conversation":
            return await self._decide_conversation(intent, context)
        
        # 6. Aprendizado
        if intent_type == "learning":
            return await self._decide_learning(intent, context)
        
        # 7. Desconhecido - pede clarificação
        return Decision(
            decision_type=DecisionType.ASK_CLARIFICATION,
            reason=f"Intenção desconhecida: {intent_type}",
            confidence=0.3
        )
    
    async def _decide_emergency(self, intent: Dict[str, Any], 
                                context: Dict[str, Any]) -> Decision:
        """Decisão para emergências."""
        return Decision(
            decision_type=DecisionType.EMERGENCY,
            target="security_agent",
            confidence=1.0,
            reason="Emergência detectada",
            data=intent.get("data", {})
        )
    
    async def _decide_command(self, intent: Dict[str, Any], 
                              context: Dict[str, Any]) -> Decision:
        """Decisão para comandos."""
        command = intent.get("data", {}).get("command", "")
        
        # Comandos do sistema
        if command.startswith("system."):
            return Decision(
                decision_type=DecisionType.EXECUTE_TOOL,
                target="system_tool",
                confidence=0.9,
                reason=f"Comando do sistema: {command}",
                data={"command": command, "params": intent.get("data", {}).get("params", {})}
            )
        
        # Comandos de automação
        if "luz" in command or "temperatura" in command or "dispositivo" in command:
            return Decision(
                decision_type=DecisionType.ROUTE_TO_AGENT,
                target="home_automation_agent",
                confidence=0.9,
                reason=f"Comando de automação: {command}",
                data={"command": command}
            )
        
        # Comandos de informação
        if "status" in command or "informação" in command:
            return Decision(
                decision_type=DecisionType.ROUTE_TO_AGENT,
                target="information_agent",
                confidence=0.9,
                reason=f"Comando de informação: {command}",
                data={"command": command}
            )
        
        # Comando genérico
        return Decision(
            decision_type=DecisionType.ROUTE_TO_AGENT,
            target="general_agent",
            confidence=0.7,
            reason=f"Comando genérico: {command}",
            data={"command": command}
        )
    
    async def _decide_question(self, intent: Dict[str, Any], 
                               context: Dict[str, Any]) -> Decision:
        """Decisão para perguntas."""
        question = intent.get("data", {}).get("question", "")
        
        # Perguntas de conhecimento
        if "o que é" in question.lower() or "quem é" in question.lower():
            return Decision(
                decision_type=DecisionType.ROUTE_TO_AGENT,
                target="knowledge_agent",
                confidence=0.9,
                reason=f"Pergunta de conhecimento: {question[:50]}...",
                data={"question": question}
            )
        
        # Perguntas de memória
        if "lembra" in question.lower() or "quando" in question.lower():
            return Decision(
                decision_type=DecisionType.ROUTE_TO_AGENT,
                target="memory_agent",
                confidence=0.8,
                reason=f"Pergunta sobre memória: {question[:50]}...",
                data={"question": question}
            )
        
        # Perguntas de planejamento
        if "como" in question.lower() or "planejar" in question.lower():
            return Decision(
                decision_type=DecisionType.CREATE_PLAN,
                target="planner",
                confidence=0.8,
                reason=f"Pergunta de planejamento: {question[:50]}...",
                data={"question": question}
            )
        
        # Pergunta genérica
        return Decision(
            decision_type=DecisionType.ROUTE_TO_AGENT,
            target="general_agent",
            confidence=0.6,
            reason=f"Pergunta genérica: {question[:50]}...",
            data={"question": question}
        )
    
    async def _decide_planning(self, intent: Dict[str, Any], 
                               context: Dict[str, Any]) -> Decision:
        """Decisão para planejamento."""
        return Decision(
            decision_type=DecisionType.CREATE_PLAN,
            target="planner",
            confidence=0.9,
            reason="Intenção de planejamento detectada",
            data=intent.get("data", {})
        )
    
    async def _decide_conversation(self, intent: Dict[str, Any], 
                                   context: Dict[str, Any]) -> Decision:
        """Decisão para conversação."""
        return Decision(
            decision_type=DecisionType.ROUTE_TO_AGENT,
            target="general_agent",
            confidence=0.7,
            reason="Conversação geral",
            data=intent.get("data", {})
        )
    
    async def _decide_learning(self, intent: Dict[str, Any], 
                               context: Dict[str, Any]) -> Decision:
        """Decisão para aprendizado."""
        return Decision(
            decision_type=DecisionType.ROUTE_TO_AGENT,
            target="learning_agent",
            confidence=0.9,
            reason="Intenção de aprendizado detectada",
            data=intent.get("data", {})
        )
    
    async def decide_emergency(self, event: Any) -> Optional[Decision]:
        """
        Decisão rápida para emergências.
        """
        return Decision(
            decision_type=DecisionType.EMERGENCY,
            target="security_agent",
            confidence=1.0,
            reason="Evento crítico",
            data={"event": event.payload if hasattr(event, 'payload') else {}}
        )