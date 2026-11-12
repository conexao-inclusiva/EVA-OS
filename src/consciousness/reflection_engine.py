"""Motor de reflexão da Consciência."""

from typing import Dict, Any, List, Optional
from datetime import datetime


class ReflectionEngine:
    """
    Motor de reflexão - auto-análise e aprendizado.
    
    Responsabilidades:
    - Analisar decisões passadas
    - Identificar padrões
    - Aprender com erros
    - Sugerir melhorias
    """
    
    def __init__(self, consciousness_manager):
        self.consciousness = consciousness_manager
        self.logger = consciousness_manager.logger
        self.event_bus = consciousness_manager.event_bus
        
        self._reflection_count = 0
        self._insights: List[Dict[str, Any]] = []
    
    async def reflect(self) -> Dict[str, Any]:
        """
        Executa um ciclo de reflexão.
        """
        self.logger.info("Iniciando ciclo de reflexão...")
        
        insights = []
        
        # 1. Analisa decisões recentes
        decisions = self.consciousness.get_decision_history(50)
        decision_insights = self._analyze_decisions(decisions)
        if decision_insights:
            insights.extend(decision_insights)
        
        # 2. Analisa padrões de intenção
        intent_insights = self._analyze_intent_patterns(decisions)
        if intent_insights:
            insights.extend(intent_insights)
        
        # 3. Analisa eficiência
        efficiency_insights = self._analyze_efficiency(decisions)
        if efficiency_insights:
            insights.extend(efficiency_insights)
        
        # 4. Gera recomendações
        recommendations = self._generate_recommendations(insights)
        
        self._reflection_count += 1
        
        # Armazena insights
        for insight in insights:
            insight["reflection_id"] = self._reflection_count
            insight["timestamp"] = datetime.now().isoformat()
            self._insights.append(insight)
        
        # Limita histórico
        if len(self._insights) > 1000:
            self._insights = self._insights[-1000:]
        
        result = {
            "reflection_id": self._reflection_count,
            "insights": insights,
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat()
        }
        
        # Publica resultado
        await self.event_bus.publish_async(
            "consciousness.reflection_complete",
            result,
            source="reflection_engine"
        )
        
        self.logger.info(f"Ciclo de reflexão concluído: {len(insights)} insights")
        
        return result
    
    def _analyze_decisions(self, decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analisa decisões passadas."""
        insights = []
        
        if not decisions:
            return insights
        
        # Conta tipos de decisão
        types = {}
        for d in decisions:
            decision = d.get("decision", {})
            decision_type = decision.get("type", "unknown")
            types[decision_type] = types.get(decision_type, 0) + 1
        
        if types:
            most_common = max(types.items(), key=lambda x: x[1])
            insights.append({
                "type": "decision_pattern",
                "message": f"Tipo de decisão mais comum: {most_common[0]} ({most_common[1]} vezes)",
                "data": types
            })
        
        # Identifica erros/baixa confiança
        low_confidence = [
            d for d in decisions
            if d.get("decision", {}).get("confidence", 1.0) < 0.5
        ]
        
        if low_confidence:
            insights.append({
                "type": "low_confidence",
                "message": f"{len(low_confidence)} decisões com baixa confiança",
                "data": {
                    "count": len(low_confidence),
                    "examples": [
                        d.get("decision", {}).get("reason", "")
                        for d in low_confidence[:3]
                    ]
                }
            })
        
        return insights
    
    def _analyze_intent_patterns(self, decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analisa padrões de intenção."""
        insights = []
        
        if not decisions:
            return insights
        
        # Conta intenções
        intents = {}
        for d in decisions:
            context = d.get("context", {})
            conversation = context.get("conversation", {})
            intent = conversation.get("intent", {}).get("type", "unknown")
            intents[intent] = intents.get(intent, 0) + 1
        
        if intents and len(intents) > 1:
            most_common = max(intents.items(), key=lambda x: x[1])
            insights.append({
                "type": "intent_pattern",
                "message": f"Intenção mais comum: {most_common[0]} ({most_common[1]} vezes)",
                "data": intents
            })
        
        return insights
    
    def _analyze_efficiency(self, decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analisa eficiência das decisões."""
        insights = []
        
        if not decisions:
            return insights
        
        # Calcula tempo médio entre decisões
        timestamps = []
        for d in decisions:
            ts = d.get("timestamp")
            if ts:
                try:
                    timestamps.append(datetime.fromisoformat(ts))
                except:
                    pass
        
        if len(timestamps) > 1:
            avg_gap = sum(
                (timestamps[i] - timestamps[i-1]).total_seconds()
                for i in range(1, len(timestamps))
            ) / (len(timestamps) - 1)
            
            if avg_gap > 60:
                insights.append({
                    "type": "efficiency",
                    "message": f"Tempo médio entre decisões: {avg_gap:.1f}s",
                    "data": {"avg_gap": avg_gap}
                })
        
        return insights
    
    def _generate_recommendations(self, insights: List[Dict[str, Any]]) -> List[str]:
        """Gera recomendações baseadas nos insights."""
        recommendations = []
        
        for insight in insights:
            if insight.get("type") == "low_confidence":
                recommendations.append(
                    "Considere melhorar o classificador de intenções para aumentar confiança"
                )
            
            if insight.get("type") == "efficiency":
                recommendations.append(
                    "Considere otimizar o tempo de resposta para decisões"
                )
        
        return recommendations
    
    async def learn_from_plan(self, plan_data: Dict[str, Any]) -> None:
        """
        Aprende com um plano concluído.
        """
        self.logger.info(f"Aprendendo com plano: {plan_data.get('plan_id', '')[:8]}")
        
        # TODO: Extrair aprendizado do plano
        pass