"""Classificador de intenções."""

from typing import Dict, Any, Optional, List
import re


class IntentClassifier:
    """
    Classifica intenções a partir de texto e contexto.
    """
    
    def __init__(self, consciousness_manager):
        self.consciousness = consciousness_manager
        self.logger = consciousness_manager.logger
        
        # Padrões de intenção
        self._patterns = {
            "emergency": [
                r"urgente", r"emergência", r"perigo", r"fogo", r"acidente",
                r"ajuda", r"socorro", r"rápido", r"agora"
            ],
            "command": [
                r"faça", r"execute", r"ligue", r"desligue", r"abra", r"feche",
                r"ative", r"desative", r"mude", r"configure", r"inicie", r"pare"
            ],
            "question": [
                r"o que", r"quem", r"quando", r"onde", r"como", r"por que",
                r"qual", r"quanto", r"pode", r"poderia", r"seria"
            ],
            "planning": [
                r"planejar", r"planeje", r"organizar", r"organize",
                r"projeto", r"construir", r"criar", r"desenvolver"
            ],
            "learning": [
                r"aprender", r"ensinar", r"explicar", r"estudar",
                r"pesquisar", r"descobrir", r"entender"
            ],
            "conversation": [
                r"oi", r"olá", r"e aí", r"tudo bem", r"como vai",
                r"bom dia", r"boa tarde", r"boa noite"
            ]
        }
    
    async def classify(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classifica a intenção de um texto.
        """
        text_lower = text.lower()
        
        # Calcula scores para cada intenção
        scores = {}
        for intent, patterns in self._patterns.items():
            score = 0
            for pattern in patterns:
                if pattern in text_lower:
                    score += 1
            scores[intent] = score
        
        # Encontra a intenção com maior score
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                # Pode ter múltiplas intenções
                top_intents = [
                    (intent, score / len(self._patterns[intent]))
                    for intent, score in scores.items()
                    if score > 0
                ]
                
                # Ordena por score
                top_intents.sort(key=lambda x: x[1], reverse=True)
                
                primary_intent = top_intents[0][0]
                confidence = min(1.0, top_intents[0][1] * 2)
                
                # Ajusta confiança baseada no comprimento do texto
                if len(text) < 3:
                    confidence = min(confidence, 0.5)
                
                # Ajusta confiança baseada no contexto
                context_intent = context.get("intent", {}).get("current")
                if context_intent and context_intent == primary_intent:
                    confidence = min(1.0, confidence + 0.2)
                
                return {
                    "type": primary_intent,
                    "confidence": confidence,
                    "all_intents": top_intents,
                    "text": text
                }
        
        # Se não classificou, assume conversação
        return {
            "type": "conversation",
            "confidence": 0.3,
            "all_intents": [],
            "text": text
        }
    
    def _get_context_intent(self, context: Dict[str, Any]) -> Optional[str]:
        """Obtém a intenção atual do contexto."""
        return context.get("conversation", {}).get("current_intent")