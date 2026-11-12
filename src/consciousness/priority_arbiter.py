"""Árbitro de prioridades."""

from typing import Dict, Any, List, Optional
from datetime import datetime


class PriorityArbiter:
    """
    Arbitra prioridades entre múltiplas demandas.
    """
    
    def __init__(self, consciousness_manager):
        self.consciousness = consciousness_manager
        self.logger = consciousness_manager.logger
    
    def arbitrate(self, demands: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Arbitra entre múltiplas demandas.
        Retorna a demanda de maior prioridade.
        """
        if not demands:
            return {}
        
        if len(demands) == 1:
            return demands[0]
        
        # Calcula score para cada demanda
        scored = []
        for demand in demands:
            score = self._calculate_score(demand)
            scored.append((score, demand))
        
        # Ordena por score (maior primeiro)
        scored.sort(key=lambda x: x[0], reverse=True)
        
        return scored[0][1]
    
    def _calculate_score(self, demand: Dict[str, Any]) -> float:
        """
        Calcula score de prioridade.
        """
        score = 0.0
        
        # 1. Prioridade explícita
        priority = demand.get("priority", 5)
        score += (10 - priority) * 0.5
        
        # 2. Urgência
        urgency = demand.get("urgency", 0)
        score += urgency * 0.3
        
        # 3. Fonte (usuário tem mais peso)
        source = demand.get("source", "system")
        if source == "user":
            score += 2.0
        elif source == "admin":
            score += 3.0
        elif source == "system":
            score += 1.0
        
        # 4. Tempo de espera
        created_at = demand.get("created_at")
        if created_at:
            wait_time = (datetime.now() - datetime.fromisoformat(created_at)).total_seconds()
            score += min(wait_time / 60, 5.0)  # Max 5 pontos por espera
        
        # 5. Tipo de demanda
        demand_type = demand.get("type", "unknown")
        type_weights = {
            "emergency": 10.0,
            "command": 8.0,
            "planning": 6.0,
            "question": 4.0,
            "conversation": 2.0
        }
        score += type_weights.get(demand_type, 1.0)
        
        return score