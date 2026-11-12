"""Extrator de padrões."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import re


class PatternExtractor:
    """
    Extrai padrões de interações.
    
    Tipos de padrões:
    - Frequência de palavras
    - Tópicos recorrentes
    - Padrões de horário
    - Sequências de ações
    - Padrões de perguntas
    """
    
    def __init__(self, learning_manager):
        self.learning_manager = learning_manager
        self.logger = learning_manager.logger
        
        self._message_history: List[Dict[str, Any]] = []
        self._patterns: List[Dict[str, Any]] = []
        self._word_freq: Counter = Counter()
        self._topic_freq: Counter = Counter()
        self._hourly_freq: Counter = Counter()
        self._question_patterns: List[str] = []
    
    async def process_message(self, text: str, user: str) -> None:
        """
        Processa uma mensagem para extração de padrões.
        """
        timestamp = datetime.now()
        
        self._message_history.append({
            "text": text,
            "user": user,
            "timestamp": timestamp
        })
        
        # Limita histórico
        if len(self._message_history) > 1000:
            self._message_history = self._message_history[-1000:]
        
        # Atualiza frequência de palavras
        words = re.findall(r'\w+', text.lower())
        for word in words:
            if len(word) > 3:
                self._word_freq[word] += 1
        
        # Atualiza frequência de tópicos
        topics = self._extract_topics(text)
        for topic in topics:
            self._topic_freq[topic] += 1
        
        # Atualiza frequência horária
        hour = timestamp.hour
        self._hourly_freq[hour] += 1
        
        # Detecta padrões de pergunta
        if "?" in text or text.lower().startswith(("o que", "quem", "quando", "onde", "como", "por que")):
            self._question_patterns.append(text[:100])
    
    async def extract(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Extrai padrões.
        """
        patterns = []
        
        # 1. Palavras mais frequentes
        top_words = self._word_freq.most_common(10)
        if top_words:
            patterns.append({
                "type": "word_frequency",
                "name": "Palavras mais frequentes",
                "description": f"As palavras mais usadas são: {', '.join([w for w, _ in top_words[:5]])}",
                "data": top_words,
                "frequency": sum(c for _, c in top_words),
                "confidence": 0.8
            })
        
        # 2. Tópicos mais frequentes
        top_topics = self._topic_freq.most_common(5)
        if top_topics:
            patterns.append({
                "type": "topic_frequency",
                "name": "Tópicos mais frequentes",
                "description": f"Os tópicos mais comuns são: {', '.join([t for t, _ in top_topics])}",
                "data": top_topics,
                "frequency": sum(c for _, c in top_topics),
                "confidence": 0.7
            })
        
        # 3. Horários de pico
        peak_hours = self._hourly_freq.most_common(3)
        if peak_hours:
            patterns.append({
                "type": "peak_hours",
                "name": "Horários de pico",
                "description": f"Maior atividade nos horários: {', '.join([f'{h}h' for h, _ in peak_hours])}",
                "data": peak_hours,
                "confidence": 0.6
            })
        
        # 4. Padrões de pergunta
        if len(self._question_patterns) > 10:
            question_types = self._analyze_question_patterns()
            if question_types:
                patterns.append({
                    "type": "question_patterns",
                    "name": "Padrões de perguntas",
                    "description": f"Tipos de pergunta: {', '.join(question_types.keys())}",
                    "data": question_types,
                    "confidence": 0.7
                })
        
        self._patterns = patterns
        return patterns[:limit]
    
    def _extract_topics(self, text: str) -> List[str]:
        """
        Extrai tópicos de um texto.
        """
        topics = []
        
        # Palavras-chave comuns
        common_topics = {
            "luz": ["luz", "iluminação", "lâmpada"],
            "temperatura": ["temperatura", "frio", "calor", "ar"],
            "música": ["música", "som", "playlist"],
            "programação": ["programar", "código", "python", "javascript"],
            "estudo": ["estudar", "aprender", "curso", "matéria"],
            "compras": ["comprar", "mercado", "lista"]
        }
        
        text_lower = text.lower()
        
        for topic, keywords in common_topics.items():
            for keyword in keywords:
                if keyword in text_lower:
                    topics.append(topic)
                    break
        
        return topics
    
    def _analyze_question_patterns(self) -> Dict[str, int]:
        """
        Analisa padrões de perguntas.
        """
        patterns = {}
        
        for q in self._question_patterns[-100:]:
            q_lower = q.lower()
            
            if q_lower.startswith("o que"):
                patterns["definição"] = patterns.get("definição", 0) + 1
            elif q_lower.startswith("como"):
                patterns["processo"] = patterns.get("processo", 0) + 1
            elif q_lower.startswith("quando"):
                patterns["tempo"] = patterns.get("tempo", 0) + 1
            elif q_lower.startswith("onde"):
                patterns["local"] = patterns.get("local", 0) + 1
            elif q_lower.startswith("quem"):
                patterns["pessoa"] = patterns.get("pessoa", 0) + 1
            elif q_lower.startswith("por que"):
                patterns["motivo"] = patterns.get("motivo", 0) + 1
        
        return {k: v for k, v in patterns.items() if v > 0}