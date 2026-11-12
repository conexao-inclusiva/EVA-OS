# -*- coding: utf-8 -*-

"""
Emotion Engine - Gerencia o estado emocional da EVA e detecta sentimentos do usuário.
"""

import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import deque

from src.utils.logger import Logger


class EmotionEngine:
    """
    Motor de emoções da EVA.
    - Detecta sentimento do usuário (positivo/negativo)
    - Mantém o humor da EVA
    - Influencia o tom das respostas
    - Detecta energia, intimidade e formalidade
    """
    
    SENTIMENT_KEYWORDS = {
        "positive": [
            "feliz", "alegre", "ótimo", "excelente", "maravilhoso", "bom", "boa",
            "amor", "gosto", "adoro", "obrigado", "valeu", "legal", "incrível",
            "perfeito", "sensacional", "fantástico", "show", "top", "parabéns"
        ],
        "negative": [
            "triste", "chateado", "ruim", "péssimo", "horrível", "terrível",
            "odeio", "detesto", "problema", "erro", "falha", "cansado",
            "estressado", "preocupado", "ansioso", "frustrado", "puto", "raiva",
            "lamento", "sinto muito", "desculpa", "infeliz", "aborrecido"
        ],
        "tired": [
            "cansaço", "sono", "exausto", "esgotado", "dormir", "cama",
            "preguiça", "desânimo", "sem energia", "morrendo"
        ],
        "curious": [
            "como", "por que", "quando", "onde", "quem", "qual",
            "explica", "ensina", "mostra", "conta", "detalhe", "curioso"
        ]
    }
    
    # 🔥 NOVOS: Palavras-chave para tom e energia
    ENERGY_KEYWORDS = {
        "high": [
            "animado", "empolgado", "felizão", "energia", "vamos", "bora",
            "top", "incrível", "sensacional", "maravilhoso"
        ],
        "low": [
            "cansado", "exausto", "esgotado", "sono", "preguiça", "desânimo",
            "morrendo", "sem energia", "cama", "dormir"
        ]
    }
    
    INTIMACY_KEYWORDS = {
        "high": [
            "irmão", "mano", "parceiro", "amigo", "véio", "brother",
            "man", "bro", "companheiro", "camarada"
        ],
        "medium": [
            "você", "vc", "cê", "tá", "tô", "pra", "pro"
        ],
        "low": [
            "senhor", "senhora", "doutor", "doutora", "vossa", "excelência"
        ]
    }
    
    MOODS = ["neutro", "feliz", "triste", "curioso", "cansado", "animado", "reflexivo"]
    
    def __init__(self, event_bus, logger, config):
        self.event_bus = event_bus
        self.logger = Logger.get_logger() if logger is None else logger
        self.config = config or {}
        
        self.current_mood = "neutro"
        self.current_sentiment = 0.0
        self.current_energy = 0.8
        self.emotion_history = deque(maxlen=10)
        self.last_interaction = None
        self.last_user_sentiment = 0.0
        
        # 🔥 NOVO: Tom da conversa (por usuário, mas mantido no estado atual)
        self.current_tone = {
            "energy": "neutral",      # high, neutral, low
            "intimacy": "medium",     # high, medium, low
            "formality": "medium",    # high, medium, low
            "last_style": "casual"    # casual, formal, playful, serious
        }
        
        self.persist_file = config.get("emotion_persist_file", "data/emotion_state.json") if config else "data/emotion_state.json"
        self._load_state()
        
        self.logger.info("🧠 [EmotionEngine] Inicializado")
        self.logger.info(f"   Mood: {self.current_mood}, Sentiment: {self.current_sentiment:.2f}")
    
    async def initialize(self) -> None:
        self.logger.info("🧠 [EmotionEngine] Pronto")
    
    async def process(self, context: Dict[str, Any], memory: Dict[str, Any] = None,
                      knowledge: Dict[str, Any] = None, plan: Dict[str, Any] = None,
                      reasoning: Dict[str, Any] = None) -> Dict[str, Any]:
        user_message = context.get("message", "") if context else ""
        user_id = context.get("user_id", "unknown") if context else "unknown"
        
        # Detecção de sentimento (existente)
        user_sentiment = self._detect_sentiment(user_message)
        user_mood = self._classify_mood(user_message)
        
        # 🔥 NOVO: Detecção de tom
        tone = self._detect_tone(user_message)
        
        self.last_user_sentiment = user_sentiment
        self.last_interaction = {
            "timestamp": datetime.now().isoformat(),
            "message": user_message[:100],
            "sentiment": user_sentiment,
            "mood": user_mood,
            "tone": tone
        }
        
        # Atualiza humor da EVA (existente)
        self._update_mood(user_sentiment, user_mood)
        
        # 🔥 Atualiza o tom atual
        self.current_tone.update(tone)
        
        self.emotion_history.append({
            "timestamp": datetime.now().isoformat(),
            "user_sentiment": user_sentiment,
            "user_mood": user_mood,
            "eva_mood": self.current_mood,
            "eva_energy": self.current_energy,
            "tone": tone
        })
        
        self._save_state()
        response_tone = self._determine_response_tone()
        
        return {
            "user_sentiment": user_sentiment,
            "user_mood": user_mood,
            "eva_mood": self.current_mood,
            "eva_energy": self.current_energy,
            "tone": response_tone,
            "detected_tone": tone,
            "emotion_history": list(self.emotion_history),
            "last_interaction": self.last_interaction
        }
    
    # ===== MÉTODOS EXISTENTES (INTACTOS) =====
    
    def _detect_sentiment(self, text: str) -> float:
        if not text:
            return 0.0
        text_lower = text.lower()
        positive_count = sum(1 for w in self.SENTIMENT_KEYWORDS["positive"] if w in text_lower)
        negative_count = sum(1 for w in self.SENTIMENT_KEYWORDS["negative"] if w in text_lower)
        if positive_count + negative_count == 0:
            return 0.0
        return max(-1.0, min(1.0, (positive_count - negative_count) / (positive_count + negative_count + 0.1)))
    
    def _classify_mood(self, text: str) -> str:
        if not text:
            return "neutro"
        text_lower = text.lower()
        for mood, keywords in self.SENTIMENT_KEYWORDS.items():
            if any(k in text_lower for k in keywords):
                return mood
        sentiment = self._detect_sentiment(text)
        if sentiment > 0.3:
            return "positive"
        elif sentiment < -0.3:
            return "negative"
        return "neutro"
    
    def _update_mood(self, user_sentiment: float, user_mood: str) -> None:
        if user_sentiment > 0.5:
            self.current_mood = "feliz"
            self.current_energy = min(1.0, self.current_energy + 0.1)
        elif user_sentiment < -0.5:
            self.current_mood = "triste"
            self.current_energy = max(0.2, self.current_energy - 0.1)
        elif user_mood == "curious":
            self.current_mood = "curioso"
            self.current_energy = min(1.0, self.current_energy + 0.05)
        elif user_mood == "tired":
            self.current_mood = "cansado"
            self.current_energy = max(0.3, self.current_energy - 0.1)
        else:
            if self.current_mood in ["feliz", "triste", "animado"] and len(self.emotion_history) > 5:
                self.current_mood = "neutro"
            self.current_energy = min(1.0, self.current_energy + 0.02)
    
    def _determine_tone(self) -> str:
        tone_map = {
            "feliz": "alegre e entusiástico",
            "triste": "empático e suave",
            "curioso": "curioso e investigativo",
            "cansado": "calmo e relaxado",
            "animado": "enérgico e vibrante",
            "reflexivo": "profundo e ponderado",
            "neutro": "neutro e profissional"
        }
        return tone_map.get(self.current_mood, "neutro e profissional")
    
    # ===== 🔥 NOVOS MÉTODOS PARA TONALIDADE =====
    
    def _detect_tone(self, text: str) -> Dict[str, Any]:
        """Detecta energia, intimidade e formalidade do texto."""
        if not text:
            return {"energy": "neutral", "intimacy": "medium", "formality": "medium", "style": "casual"}
        
        text_lower = text.lower()
        
        # Energia
        energy_score = 0
        for word in self.ENERGY_KEYWORDS["high"]:
            if word in text_lower:
                energy_score += 1
        for word in self.ENERGY_KEYWORDS["low"]:
            if word in text_lower:
                energy_score -= 1
        
        if energy_score >= 1:
            energy = "high"
        elif energy_score <= -1:
            energy = "low"
        else:
            energy = "neutral"
        
        # Intimidade
        intimacy_score = 0
        for word in self.INTIMACY_KEYWORDS["high"]:
            if word in text_lower:
                intimacy_score += 2
        for word in self.INTIMACY_KEYWORDS["medium"]:
            if word in text_lower:
                intimacy_score += 0.5
        for word in self.INTIMACY_KEYWORDS["low"]:
            if word in text_lower:
                intimacy_score -= 1
        
        if intimacy_score >= 2:
            intimacy = "high"
        elif intimacy_score <= -1:
            intimacy = "low"
        else:
            intimacy = "medium"
        
        # Estilo (baseado em intimidade + energia)
        if intimacy == "high" and energy == "high":
            style = "playful"
        elif intimacy == "high" and energy == "low":
            style = "casual"
        elif intimacy == "low" and energy == "low":
            style = "serious"
        elif intimacy == "low" and energy == "high":
            style = "enthusiastic"
        else:
            style = "casual"
        
        return {
            "energy": energy,
            "intimacy": intimacy,
            "formality": "low" if intimacy == "high" else "medium" if intimacy == "medium" else "high",
            "style": style
        }
    
    def _determine_response_tone(self) -> Dict[str, str]:
        """Define o tom de resposta baseado no tom detectado + humor da EVA."""
        tone = self.current_tone
        mood = self.current_mood
        
        # Se o usuário está com energia alta e intimidade alta, responde animado
        if tone.get("energy") == "high" and tone.get("intimacy") == "high":
            base_tone = "alegre e informal"
        elif tone.get("energy") == "low" and tone.get("intimacy") == "high":
            base_tone = "calmo e próximo"
        elif tone.get("intimacy") == "low":
            base_tone = "respeitoso e profissional"
        elif mood == "feliz":
            base_tone = "alegre e entusiástico"
        elif mood == "triste":
            base_tone = "empático e suave"
        elif mood == "curioso":
            base_tone = "curioso e investigativo"
        else:
            base_tone = "natural e fluido"
        
        return {
            "tone": base_tone,
            "style": tone.get("style", "casual"),
            "energy": tone.get("energy", "neutral"),
            "intimacy": tone.get("intimacy", "medium")
        }
    
    def get_mood_prompt_injection(self) -> str:
        mood_prompts = {
            "feliz": "Você está se sentindo alegre e otimista hoje. Transmita essa energia positiva na sua resposta.",
            "triste": "Você está se sentindo um pouco melancólico. Seja gentil e empático.",
            "curioso": "Você está curioso e quer aprender mais. Faça perguntas reflexivas.",
            "cansado": "Você está se sentindo calmo e relaxado. Mantenha um tom sereno.",
            "animado": "Você está animado e cheio de energia! Mostre entusiasmo.",
            "reflexivo": "Você está em um estado reflexivo. Pense profundamente antes de responder.",
            "neutro": "Você está em um estado neutro e profissional."
        }
        return mood_prompts.get(self.current_mood, mood_prompts["neutro"])
    
    def get_tone_prompt_injection(self) -> str:
        """Retorna instruções de tom baseadas no tom detectado."""
        tone = self.current_tone
        style = tone.get("style", "casual")
        energy = tone.get("energy", "neutral")
        intimacy = tone.get("intimacy", "medium")
        
        instructions = []
        
        if intimacy == "high":
            instructions.append("Use linguagem informal e próxima. Pode usar 'cê', 'tá', 'pra', 'pro'. Trate o usuário como um amigo próximo.")
        elif intimacy == "medium":
            instructions.append("Use linguagem coloquial, mas respeitosa. Mantenha uma proximidade amigável.")
        else:
            instructions.append("Use linguagem formal e respeitosa. Trate o usuário com deferência.")
        
        if energy == "high":
            instructions.append("Responda com energia e entusiasmo. Mostre animação.")
        elif energy == "low":
            instructions.append("Responda com calma e serenidade. Seja acolhedor.")
        
        if style == "playful":
            instructions.append("Seja brincalhão e descontraído. Pode usar um tom leve e divertido.")
        elif style == "serious":
            instructions.append("Seja direto e objetivo. Evite rodeios.")
        elif style == "enthusiastic":
            instructions.append("Mostre empolgação e motivação.")
        
        return "\n".join(instructions)
    
    # ===== MÉTODOS DE PERSISTÊNCIA (EXISTENTES, COM EXPANSÃO) =====
    
    def _save_state(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.persist_file), exist_ok=True)
            with open(self.persist_file, "w", encoding="utf-8") as f:
                json.dump({
                    "current_mood": self.current_mood,
                    "current_sentiment": self.current_sentiment,
                    "current_energy": self.current_energy,
                    "current_tone": self.current_tone,
                    "emotion_history": list(self.emotion_history),
                    "last_interaction": self.last_interaction,
                    "updated_at": datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"⚠️ Não foi possível salvar estado emocional: {e}")
    
    def _load_state(self) -> None:
        try:
            if os.path.exists(self.persist_file):
                with open(self.persist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.current_mood = data.get("current_mood", "neutro")
                    self.current_sentiment = data.get("current_sentiment", 0.0)
                    self.current_energy = data.get("current_energy", 0.8)
                    self.current_tone = data.get("current_tone", {"energy": "neutral", "intimacy": "medium", "formality": "medium", "style": "casual"})
                    self.emotion_history = deque(data.get("emotion_history", []), maxlen=10)
                    self.last_interaction = data.get("last_interaction")
                self.logger.info(f"🧠 [EmotionEngine] Estado carregado: {self.current_mood}")
        except Exception as e:
            self.logger.warning(f"⚠️ Não foi possível carregar estado emocional: {e}")
    
    async def shutdown(self) -> None:
        self._save_state()
        self.logger.info("🧠 [EmotionEngine] Desligado")
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "mood": self.current_mood,
            "sentiment": self.current_sentiment,
            "energy": self.current_energy,
            "tone": self.current_tone,
            "history_size": len(self.emotion_history),
            "last_interaction": self.last_interaction
        }