"""Agregador de contexto."""

from typing import Dict, Any, Optional, List
from datetime import datetime


class ContextAggregator:
    """
    Agrega todas as camadas de contexto em um único objeto.
    Prepara o contexto para uso por IA, agentes e ferramentas.
    """
    
    def __init__(self, context_manager):
        self.context_manager = context_manager
    
    def aggregate(self) -> Dict[str, Any]:
        """
        Agrega todo o contexto em um único objeto estruturado.
        
        Retorna:
        {
            "user": {...},
            "environment": {...},
            "conversation": {...},
            "temporal": {...},
            "system": {...},
            "summary": "...",  # Texto resumido para IA
            "timestamp": "..."
        }
        """
        # Coleta de todas as camadas
        user = self.context_manager.user.get_all()
        environment = self.context_manager.environment.get_all()
        conversation = self.context_manager.conversation.get_all()
        temporal = self.context_manager.temporal.get_all()
        system = self.context_manager.system.get_all()
        
        # Constrói o objeto agregado
        aggregated = {
            "user": self._extract_user_summary(user),
            "environment": self._extract_environment_summary(environment),
            "conversation": self._extract_conversation_summary(conversation),
            "temporal": self._extract_temporal_summary(temporal),
            "system": self._extract_system_summary(system),
            "timestamp": datetime.now().isoformat()
        }
        
        # Gera texto resumido para IA
        aggregated["summary"] = self._generate_summary(aggregated)
        
        return aggregated
    
    def _extract_user_summary(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai resumo do usuário."""
        return {
            "current": user.get("current_user"),
            "role": "admin" if user.get("current_user") == "alberto" else "user",
            "preferences": user.get("users", {}).get(
                user.get("current_user", ""), {}
            ).get("preferences", {}),
            "active_users": user.get("active_users", [])
        }
    
    def _extract_environment_summary(self, env: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai resumo do ambiente."""
        return {
            "location": env.get("location", "Casa"),
            "room": env.get("room"),
            "temperature": env.get("temperature", 0.0),
            "light_status": self._get_light_status(env),
            "devices": len(env.get("devices", {})),
            "sensors": len(env.get("sensors", {}))
        }
    
    def _get_light_status(self, env: Dict[str, Any]) -> str:
        """Obtém resumo do status das luzes."""
        lights = env.get("lights", {})
        if not lights:
            return "desconhecido"
        
        on_count = sum(1 for l in lights.values() if l.get("on", False))
        total = len(lights)
        
        if on_count == 0:
            return "todas apagadas"
        elif on_count == total:
            return "todas acesas"
        else:
            return f"{on_count}/{total} acesas"
    
    def _extract_conversation_summary(self, conv: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai resumo da conversa."""
        return {
            "topic": conv.get("current_topic"),
            "intent": conv.get("detected_intent"),
            "message_count": conv.get("message_count", 0),
            "last_messages": conv.get("history", [])[-3:] if conv.get("history") else []
        }
    
    def _extract_temporal_summary(self, temporal: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai resumo temporal."""
        return {
            "time": temporal.get("time"),
            "date": temporal.get("date"),
            "period": temporal.get("period"),
            "day": temporal.get("day_name"),
            "is_weekend": temporal.get("is_weekend", False),
            "is_school_day": temporal.get("is_school_day", False),
            "season": temporal.get("season")
        }
    
    def _extract_system_summary(self, system: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai resumo do sistema."""
        return {
            "state": system.get("state", "UNKNOWN"),
            "uptime": system.get("uptime", 0),
            "resources": {
                "cpu": system.get("cpu_usage", 0),
                "memory": system.get("memory_usage", 0),
                "disk": system.get("disk_usage", 0)
            },
            "active_modules": system.get("active_modules", [])
        }
    
    def _generate_summary(self, aggregated: Dict[str, Any]) -> str:
        """
        Gera um texto resumido para uso em IA.
        """
        parts = []
        
        # Usuário
        user = aggregated["user"]
        if user.get("current"):
            parts.append(f"Usuário: {user['current']} ({user.get('role', 'guest')})")
        
        # Temporal
        temporal = aggregated["temporal"]
        parts.append(f"Horário: {temporal.get('time')} - {temporal.get('period')}")
        parts.append(f"Dia: {temporal.get('day')}")
        if temporal.get("is_weekend"):
            parts.append("(Fim de semana)")
        if temporal.get("is_school_day"):
            parts.append("(Dia de escola)")
        
        # Ambiente
        env = aggregated["environment"]
        if env.get("room"):
            parts.append(f"Local: {env['room']}")
        if env.get("temperature"):
            parts.append(f"Temperatura: {env['temperature']:.1f}°C")
        if env.get("light_status"):
            parts.append(f"Luzes: {env['light_status']}")
        
        # Conversa
        conv = aggregated["conversation"]
        if conv.get("topic"):
            parts.append(f"Tópico: {conv['topic']}")
        if conv.get("intent"):
            parts.append(f"Intenção: {conv['intent']}")
        
        # Sistema
        system = aggregated["system"]
        parts.append(f"Sistema: {system.get('state')}")
        
        return "\n".join(parts)
    
    def to_string(self) -> str:
        """Gera uma string de contexto para uso em LLM."""
        aggregated = self.aggregate()
        return aggregated.get("summary", "")