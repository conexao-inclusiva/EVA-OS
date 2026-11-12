"""Analisador de contexto."""

from typing import Dict, Any, Optional


class ContextAnalyzer:
    """
    Analisa o contexto para auxiliar decisões.
    """
    
    def __init__(self, consciousness_manager):
        self.consciousness = consciousness_manager
        self.logger = consciousness_manager.logger
        self.context_manager = consciousness_manager.context_manager
    
    async def analyze(self, event: Any) -> Dict[str, Any]:
        """
        Analisa o contexto atual.
        """
        context = {
            "user": {},
            "environment": {},
            "temporal": {},
            "conversation": {},
            "system": {},
            "event": {}
        }
        
        # 1. Contexto do usuário
        user_context = self.context_manager.user.get_all()
        context["user"] = {
            "current": user_context.get("current_user"),
            "active_users": user_context.get("active_users", [])
        }
        
        # 2. Contexto do ambiente
        env_context = self.context_manager.environment.get_all()
        context["environment"] = {
            "location": env_context.get("location"),
            "room": env_context.get("room"),
            "temperature": env_context.get("temperature"),
            "light_status": self._get_light_status(env_context)
        }
        
        # 3. Contexto temporal
        temporal_context = self.context_manager.temporal.get_all()
        context["temporal"] = {
            "period": temporal_context.get("period"),
            "is_weekend": temporal_context.get("is_weekend"),
            "is_school_day": temporal_context.get("is_school_day"),
            "season": temporal_context.get("season")
        }
        
        # 4. Contexto da conversa
        conv_context = self.context_manager.conversation.get_all()
        context["conversation"] = {
            "topic": conv_context.get("current_topic"),
            "message_count": conv_context.get("message_count", 0),
            "last_messages": conv_context.get("history", [])[-3:]
        }
        
        # 5. Contexto do sistema
        sys_context = self.context_manager.system.get_all()
        context["system"] = {
            "state": sys_context.get("state"),
            "active_modules": sys_context.get("active_modules", [])
        }
        
        # 6. Contexto do evento
        if hasattr(event, 'payload'):
            context["event"] = {
                "source": event.source,
                "type": event.type,
                "payload": event.payload
            }
        
        return context
    
    def _get_light_status(self, env_context: Dict[str, Any]) -> str:
        """Obtém status das luzes."""
        lights = env_context.get("lights", {})
        if not lights:
            return "unknown"
        
        on_count = sum(1 for l in lights.values() if l.get("on", False))
        total = len(lights)
        
        if on_count == 0:
            return "all_off"
        elif on_count == total:
            return "all_on"
        else:
            return f"{on_count}/{total}_on"