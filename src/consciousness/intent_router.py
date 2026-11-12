"""Roteador de intenções."""

from typing import Dict, Any, Optional
from datetime import datetime

from src.kernel.events import Event
from src.consciousness.decision_engine import Decision, DecisionType


class IntentRouter:
    """
    Roteia intenções para o destino apropriado.
    """
    
    def __init__(self, consciousness_manager):
        self.consciousness = consciousness_manager
        self.logger = consciousness_manager.logger
        self.event_bus = consciousness_manager.event_bus
    
    async def route(self, decision: Decision, context: Dict[str, Any]) -> None:
        """
        Roteia uma decisão para o destino apropriado.
        """
        self.logger.debug(f"Roteando decisão: {decision.type.value} -> {decision.target}")
        
        if decision.type == DecisionType.ROUTE_TO_AGENT:
            await self._route_to_agent(decision, context)
        
        elif decision.type == DecisionType.CREATE_PLAN:
            await self._route_to_planner(decision, context)
        
        elif decision.type == DecisionType.EXECUTE_TOOL:
            await self._route_to_tool(decision, context)
        
        elif decision.type == DecisionType.RESPOND:
            await self._route_to_response(decision, context)
        
        elif decision.type == DecisionType.ASK_CLARIFICATION:
            await self._ask_clarification(decision, context)
        
        elif decision.type == DecisionType.EMERGENCY:
            await self._route_emergency(decision, context)
        
        elif decision.type == DecisionType.REFLECT:
            await self._route_to_reflection(decision, context)
        
        else:
            self.logger.warning(f"Tipo de decisão não reconhecido: {decision.type}")
    
    async def _route_to_agent(self, decision: Decision, context: Dict[str, Any]) -> None:
        """Roteia para um agente."""
        await self.event_bus.publish_async(
            f"agent.{decision.target}",
            {
                "decision": decision.to_dict(),
                "context": context,
                "timestamp": datetime.now().isoformat()
            },
            source="consciousness"
        )
        
        self.logger.info(f"Roteado para agente: {decision.target}")
    
    async def _route_to_planner(self, decision: Decision, context: Dict[str, Any]) -> None:
        """Roteia para o Planner."""
        goal_data = {
            "title": decision.data.get("question", "Objetivo"),
            "description": decision.data.get("description", decision.reason),
            "goal_type": "oneshot",
            "priority": 5,
            "created_by": "consciousness",
            "context": decision.data
        }
        
        await self.event_bus.publish_async(
            "planner.create_goal",
            {
                "goal": goal_data,
                "context": context,
                "timestamp": datetime.now().isoformat()
            },
            source="consciousness"
        )
        
        self.logger.info(f"Roteado para Planner: {goal_data['title']}")
    
    async def _route_to_tool(self, decision: Decision, context: Dict[str, Any]) -> None:
        """Roteia para uma ferramenta."""
        await self.event_bus.publish_async(
            "tool.execute",
            {
                "tool": decision.target,
                "params": decision.data.get("params", {}),
                "caller": "consciousness",
                "context": context,
                "timestamp": datetime.now().isoformat()
            },
            source="consciousness"
        )
        
        self.logger.info(f"Roteado para ferramenta: {decision.target}")
    
    async def _route_to_response(self, decision: Decision, context: Dict[str, Any]) -> None:
        """Roteia para resposta direta."""
        await self.event_bus.publish_async(
            "consciousness.response",
            {
                "response": decision.data.get("response", ""),
                "context": context,
                "timestamp": datetime.now().isoformat()
            },
            source="consciousness"
        )
    
    async def _ask_clarification(self, decision: Decision, context: Dict[str, Any]) -> None:
        """Pede clarificação ao usuário."""
        message = decision.data.get("message", "Não entendi. Pode reformular?")
        
        await self.event_bus.publish_async(
            "user.message.response",
            {
                "text": message,
                "context": context,
                "requesting_clarification": True,
                "timestamp": datetime.now().isoformat()
            },
            source="consciousness"
        )
        
        self.logger.info(f"Solicitando clarificação: {message}")
    
    async def _route_emergency(self, decision: Decision, context: Dict[str, Any]) -> None:
        """Roteia emergência."""
        # Prioridade máxima
        await self.event_bus.publish_async(
            "emergency.trigger",
            {
                "decision": decision.to_dict(),
                "context": context,
                "timestamp": datetime.now().isoformat()
            },
            source="consciousness",
            priority=0  # CRITICAL
        )
        
        self.logger.warning(f"EMERGÊNCIA roteada: {decision.reason}")
    
    async def _route_to_reflection(self, decision: Decision, context: Dict[str, Any]) -> None:
        """Roteia para reflexão."""
        await self.event_bus.publish_async(
            "consciousness.reflect",
            {
                "decision": decision.to_dict(),
                "context": context,
                "timestamp": datetime.now().isoformat()
            },
            source="consciousness"
        )