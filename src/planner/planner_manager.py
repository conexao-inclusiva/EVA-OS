"""Gerenciador de Planejamento - FASE 4 com Sistema de Confiança."""

from typing import Dict, Any, Optional, List
from datetime import datetime
from src.core.event_types import EventType
from src.kernel.events import Event, EventBus


class PlannerManager:
    """
    Gerenciador de Planejamento - com Sistema de Confiança.
    
    Responsabilidades:
    - Decidir o que fazer com a mensagem
    - Criar um plano de ação
    - Avaliar confiança do conhecimento
    - Definir estratégia baseada em confiança
    """
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self._running = False
    
    async def initialize(self) -> None:
        self.logger.info("📋 [PlannerManager] Inicializando...")
        self._running = True
        self.logger.info("📋 [PlannerManager] Inicializado")
    
    async def process(self, context: Dict, memory: Dict, knowledge: Dict) -> Dict[str, Any]:
        """Cria um plano baseado no contexto, memória e conhecimento."""
        self.logger.info("📋 [PlannerManager] Processando...")
        
        intent = context.get("intent", "unknown")
        query_type = context.get("query_type", "general")
        
        # ===== SISTEMA DE CONFIANÇA =====
        confidence = self._calculate_confidence(knowledge, memory, context)
        self.logger.info(f"📋 [PlannerManager] Confiança: {confidence}%")
        
        # ===== ESTRATÉGIA BASEADA EM CONFIANÇA =====
        if confidence >= 80:
            strategy = "answer_with_confidence"
        elif confidence >= 50:
            strategy = "answer_with_context"
        elif confidence >= 20:
            strategy = "ask_clarification"
        else:
            strategy = "ask_question"
        
        # ===== PLANO =====
        plan = await self._create_plan(intent, query_type, confidence, strategy)
        
        plan_data = {
            "plan": plan,
            "strategy": strategy,
            "confidence": confidence,
            "requires_llm": plan.get("requires_llm", True),
            "requires_action": plan.get("requires_action", False),
            "priority": plan.get("priority", "normal"),
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(f"📋 [PlannerManager] Plano: {plan.get('name')} (confiança: {confidence}%)")
        
        await self.event_bus.publish_async(
            EventType.PLAN_READY,
            {
                "context": context,
                "memory": memory,
                "knowledge": knowledge,
                "plan": plan_data,
                "timestamp": datetime.now().isoformat()
            },
            source="planner_manager"
        )
        
        return plan_data
    
    def _calculate_confidence(self, knowledge: Dict, memory: Dict, context: Dict) -> int:
        """Calcula confiança baseada no conhecimento disponível."""
        confidence = 0
        
        # 1. Conhecimento direto (peso 50%)
        facts = knowledge.get("facts", [])
        if facts:
            confidence += min(len(facts) * 15, 50)
        
        # 2. Memória contextual (peso 30%)
        history_count = memory.get("history_count", 0)
        if history_count > 0:
            confidence += min(history_count * 5, 30)
        
        # 3. Entidades identificadas (peso 20%)
        entities = context.get("entities", {})
        if entities:
            confidence += min(len(entities) * 10, 20)
        
        # Garante que fique entre 0 e 100
        return min(max(confidence, 0), 100)
    
    async def _create_plan(self, intent: str, query_type: str, confidence: int, strategy: str) -> Dict:
        """Cria o plano baseado na estratégia."""
        
        # Planos base por tipo de pergunta
        plans = {
            "direct_question": {
                "name": "answer_question",
                "requires_llm": True,
                "requires_action": False,
                "priority": "high",
                "steps": [
                    "Buscar conhecimento específico",
                    "Verificar memória de contexto",
                    "Gerar resposta direta"
                ],
                "expected_output": "resposta informativa"
            },
            "direct_command": {
                "name": "execute_command",
                "requires_llm": True,
                "requires_action": True,
                "priority": "high",
                "steps": [
                    "Validar comando",
                    "Executar ação",
                    "Confirmar execução"
                ],
                "expected_output": "confirmação de execução"
            },
            "planning_request": {
                "name": "create_plan",
                "requires_llm": True,
                "requires_action": False,
                "priority": "medium",
                "steps": [
                    "Analisar objetivo",
                    "Criar plano de ação",
                    "Apresentar plano"
                ],
                "expected_output": "plano detalhado"
            },
            "learning_request": {
                "name": "teach_topic",
                "requires_llm": True,
                "requires_action": False,
                "priority": "medium",
                "steps": [
                    "Identificar tópico",
                    "Buscar conhecimento",
                    "Estruturar explicação"
                ],
                "expected_output": "explicação educativa"
            },
            "general": {
                "name": "general_conversation",
                "requires_llm": True,
                "requires_action": False,
                "priority": "low",
                "steps": [
                    "Analisar mensagem",
                    "Manter conversa natural"
                ],
                "expected_output": "resposta conversacional"
            }
        }
        
        # Seleciona plano base
        base_plan = plans.get(query_type, plans["general"])
        
        # Ajusta com base na confiança
        if confidence >= 80:
            base_plan["steps"].append("✅ Alta confiança - responder diretamente")
        elif confidence >= 50:
            base_plan["steps"].append("⚠️ Confiança média - incluir contexto")
        elif confidence >= 20:
            base_plan["steps"].append("❓ Baixa confiança - pedir clarificação")
        else:
            base_plan["steps"].append("🔄 Sem conhecimento - fazer pergunta")
        
        return base_plan
    
    async def shutdown(self) -> None:
        self.logger.info("📋 [PlannerManager] Desligando...")
        self._running = False
        self.logger.info("📋 [PlannerManager] Desligado")
    
    async def health_check(self) -> dict:
        return {"status": "running" if self._running else "stopped"}