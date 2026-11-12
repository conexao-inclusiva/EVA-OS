"""Gerenciador de Raciocínio - FASE 5 com Inferências Avançadas."""

from typing import Dict, Any, Optional, List
from datetime import datetime
from src.core.event_types import EventType
from src.kernel.events import Event, EventBus


class ReasoningManager:
    """
    Gerenciador de Raciocínio - FASE 5.
    
    Responsabilidades:
    - Raciocinar sobre o contexto
    - Inferir informações implícitas
    - Fazer conexões lógicas
    """
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self._running = False
    
    async def initialize(self) -> None:
        self.logger.info("🧠 [ReasoningManager] Inicializando...")
        self._running = True
        self.logger.info("🧠 [ReasoningManager] Inicializado")
    
    async def process(self, context: Dict, memory: Dict, knowledge: Dict, plan: Dict) -> Dict[str, Any]:
        """Raciocina sobre os dados disponíveis."""
        self.logger.info("🧠 [ReasoningManager] Processando...")
        
        message = context.get("message", "")
        intent = context.get("intent", "unknown")
        
        # ===== INFERÊNCIAS AVANÇADAS =====
        inferences = {
            "has_question": "?" in message or any(w in message.lower() for w in ["o que", "quem", "como", "por que"]),
            "has_context": len(memory.get("history", [])) > 1,
            "has_knowledge": knowledge.get("total_results", 0) > 0,
            "needs_clarification": "?" in message and len(message.split()) < 5,
            "is_follow_up": self._is_follow_up(message, memory),
            "confidence_level": plan.get("confidence", 0),
            "strategy": plan.get("strategy", "unknown")
        }
        
        # ===== CONCLUSÕES LÓGICAS =====
        conclusions = self._apply_logic(inferences, context, knowledge)
        
        # ===== RECOMENDAÇÕES =====
        recommendations = self._generate_recommendations(inferences, conclusions)
        
        reasoning_data = {
            "inferences": inferences,
            "conclusions": conclusions,
            "recommendations": recommendations,
            "confidence": plan.get("confidence", 0) / 100,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(f"🧠 [ReasoningManager] {len(inferences)} inferências, {len(conclusions)} conclusões")
        
        await self.event_bus.publish_async(
            EventType.REASONING_READY,
            {
                "context": context,
                "memory": memory,
                "knowledge": knowledge,
                "plan": plan,
                "reasoning": reasoning_data,
                "timestamp": datetime.now().isoformat()
            },
            source="reasoning_manager"
        )
        
        return reasoning_data
    
    def _is_follow_up(self, message: str, memory: Dict) -> bool:
        """Verifica se é uma pergunta de acompanhamento."""
        if not memory.get("history"):
            return False
        
        follow_up_words = ["e", "mas", "também", "então", "depois", "além", "ela", "ele", "esse"]
        return any(word in message.lower() for word in follow_up_words)
    
    def _apply_logic(self, inferences: Dict, context: Dict, knowledge: Dict) -> List[str]:
        """Aplica lógica para gerar conclusões."""
        conclusions = []
        
        if inferences.get("has_question") and inferences.get("has_knowledge"):
            conclusions.append("Pergunta pode ser respondida com conhecimento existente")
        
        if inferences.get("is_follow_up") and inferences.get("has_context"):
            conclusions.append("Esta é uma pergunta de acompanhamento - manter contexto")
        
        if inferences.get("needs_clarification"):
            conclusions.append("Pergunta muito curta - considerar pedir clarificação")
        
        if inferences.get("confidence_level", 0) < 30:
            conclusions.append("Baixa confiança - considerar pedir mais informações")
        
        return conclusions
    
    def _generate_recommendations(self, inferences: Dict, conclusions: List) -> List[str]:
        """Gera recomendações baseadas nas conclusões."""
        recommendations = []
        
        if inferences.get("needs_clarification"):
            recommendations.append("Sugerir: 'Você poderia reformular sua pergunta?'")
        
        if inferences.get("confidence_level", 0) < 30:
            recommendations.append("Sugerir: 'Não tenho certeza, pode me dar mais detalhes?'")
        
        return recommendations
    
    async def shutdown(self) -> None:
        self.logger.info("🧠 [ReasoningManager] Desligando...")
        self._running = False
        self.logger.info("🧠 [ReasoningManager] Desligado")
    
    async def health_check(self) -> dict:
        return {"status": "running" if self._running else "stopped"}