"""Agente Geral - Conversação e tarefas básicas."""

from typing import Dict, Any, Optional
from datetime import datetime

from src.agents.base_agent import BaseAgent
from src.kernel.events import EventBus


class GeneralAgent(BaseAgent):
    """
    Agente Geral da EVA.
    
    Responsável por:
    - Conversação geral
    - Tarefas básicas
    - Roteamento simples
    - Interações amigáveis
    """
    
    # Atributos de plugin
    __plugin_name__ = "general_agent"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Agente geral para conversação e tarefas básicas"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["agent", "core", "conversation"]
    __plugin_capabilities__ = ["general", "conversation", "basic_tasks"]
    __plugin_requires__ = ["event_bus", "logger", "config"]
    
    def __init__(self, event_bus: EventBus, logger, config):
        super().__init__(event_bus, logger, config, name="general")
        self._greeting_count = 0
    
    async def initialize(self) -> None:
        """Inicializa o agente."""
        await super().initialize()
        self.logger.info("GeneralAgent: Pronto para conversar")
    
    async def start(self) -> None:
        """Inicia o agente."""
        await super().start()
        self.logger.info("GeneralAgent: Ativo e aguardando")
    
    async def process(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa uma tarefa.
        
        Tipos de tarefa:
        - conversation: Mensagem para conversar
        - greeting: Saudação
        - help: Ajuda
        - basic_task: Tarefa básica
        """
        task_type = task.get("type", "conversation")
        
        if task_type == "conversation":
            return await self._handle_conversation(task)
        elif task_type == "greeting":
            return await self._handle_greeting(task)
        elif task_type == "help":
            return await self._handle_help(task)
        else:
            return await self._handle_basic_task(task)
    
    async def _handle_conversation(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula conversação."""
        text = task.get("text", "")
        user = task.get("user", "unknown")
        
        self.logger.debug(f"Conversação com {user}: {text[:50]}...")
        
        # TODO: Integrar com LLM
        response = f"Recebi sua mensagem: {text[:50]}..."
        
        return {
            "type": "conversation",
            "response": response,
            "user": user,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _handle_greeting(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula saudação."""
        self._greeting_count += 1
        
        greetings = [
            "Olá! Como posso ajudar você hoje?",
            "Oi! Estou aqui para ajudar!",
            "Olá! O que você precisa?",
            "Oi! Como está?",
            "Olá! Sempre um prazer falar com você!"
        ]
        
        response = greetings[self._greeting_count % len(greetings)]
        
        return {
            "type": "greeting",
            "response": response,
            "greeting_count": self._greeting_count,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _handle_help(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula pedido de ajuda."""
        help_text = """
        Posso ajudar com:
        - Conversas e perguntas
        - Comandos básicos
        - Busca de informação
        - Lembretes
        - Automação da casa
        
        O que você gostaria?
        """
        
        return {
            "type": "help",
            "response": help_text,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _handle_basic_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula tarefa básica."""
        return {
            "type": "basic_task",
            "result": "Tarefa recebida e processada",
            "task": task,
            "timestamp": datetime.now().isoformat()
        }
    
    async def shutdown(self) -> None:
        """Desliga o agente."""
        self.logger.info(f"GeneralAgent: {self._greeting_count} saudações")
        await super().shutdown()
    
    async def health_check(self) -> Dict[str, Any]:
        """Verifica saúde do agente."""
        health = await super().health_check()
        health["greeting_count"] = self._greeting_count
        return health