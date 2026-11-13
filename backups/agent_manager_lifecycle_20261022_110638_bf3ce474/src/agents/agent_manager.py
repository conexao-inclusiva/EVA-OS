"""Gerenciador de agentes da EVA."""

import asyncio
from typing import Dict, Any, Optional, List, Type
from datetime import datetime

from src.kernel.events import Event, EventBus
from src.agents.base_agent import BaseAgent
from src.agents.agent_registry import AgentRegistry


class AgentManager:
    """
    Gerenciador de agentes da EVA.
    
    Responsabilidades:
    - Registrar agentes
    - Gerenciar ciclo de vida dos agentes
    - Selecionar agentes para tarefas
    - Monitorar saúde dos agentes
    - Distribuir tarefas
    """
    
    # Atributos de plugin
    __plugin_name__ = "agent_manager"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Gerenciador de agentes da EVA"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["core", "agents", "orchestration"]
    __plugin_capabilities__ = ["agent_management"]
    __plugin_requires__ = ["event_bus", "logger", "config"]
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        # Registro de agentes
        self.registry = AgentRegistry()
        
        # Agentes ativos
        self._agents: Dict[str, BaseAgent] = {}
        self._agent_status: Dict[str, Dict[str, Any]] = {}
        
        # Filas de tarefas por agente
        self._task_queues: Dict[str, asyncio.Queue] = {}
        self._queue_workers: Dict[str, asyncio.Task] = {}
        
        # Estado
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._monitor_interval = 30
        
        # Registra listeners
        self._register_listeners()
        
        self.logger.info("AgentManager inicializado")
    
    def _register_listeners(self) -> None:
        """Registra ouvintes de eventos."""
        # Comandos
        self.event_bus.subscribe("agent.register", self._on_register)
        self.event_bus.subscribe("agent.select", self._on_select)
        self.event_bus.subscribe("agent.assign_task", self._on_assign_task)
        self.event_bus.subscribe("agent.get_status", self._on_get_status)
        self.event_bus.subscribe("agent.list", self._on_list_agents)
        
        # Eventos automáticos para agentes específicos
        self.event_bus.subscribe("agent.general_agent", self._on_agent_event)
        self.event_bus.subscribe("agent.knowledge_agent", self._on_agent_event)
        self.event_bus.subscribe("agent.memory_agent", self._on_agent_event)
        self.event_bus.subscribe("agent.planner_agent", self._on_agent_event)
        self.event_bus.subscribe("agent.home_automation_agent", self._on_agent_event)
        self.event_bus.subscribe("agent.information_agent", self._on_agent_event)
        self.event_bus.subscribe("agent.learning_agent", self._on_agent_event)
        self.event_bus.subscribe("agent.security_agent", self._on_agent_event)
    
    async def initialize(self) -> None:
        """Inicializa o AgentManager."""
        self.logger.info("AgentManager inicializando...")
        
        # Registra agentes base
        self._register_base_agents()
        
        self._running = True
        
        # Inicia monitoramento
        self._monitor_task = asyncio.create_task(self._monitor_agents())
        
        self.logger.info(f"AgentManager inicializado com {len(self._agents)} agentes")
    
    async def start(self) -> None:
        """Inicia o AgentManager."""
        self.logger.info("AgentManager iniciando...")
        
        # Inicia todos os agentes
        for agent in self._agents.values():
            try:
                await agent.start()
            except Exception as e:
                self.logger.error(f"Erro ao iniciar agente {agent.name}: {e}")
        
        self.logger.info("AgentManager pronto")
    
    async def shutdown(self) -> None:
        """Desliga o AgentManager."""
        self.logger.info("AgentManager desligando...")
        
        self._running = False
        
        # Para workers
        for worker in self._queue_workers.values():
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
        
        # Para monitor
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # Desliga agentes
        for agent in self._agents.values():
            try:
                await agent.shutdown()
            except Exception as e:
                self.logger.error(f"Erro ao desligar agente {agent.name}: {e}")
        
        self.logger.info("AgentManager desligado")
    
    # ===== REGISTRO =====
    
    def _register_base_agents(self) -> None:
        """Registra agentes base."""
        # Importa agentes
        from src.agents.general_agent import GeneralAgent
        from src.agents.knowledge_agent import KnowledgeAgent
        from src.agents.memory_agent import MemoryAgent
        from src.agents.planner_agent import PlannerAgent
        from src.agents.home_automation_agent import HomeAutomationAgent
        from src.agents.information_agent import InformationAgent
        from src.agents.learning_agent import LearningAgent
        from src.agents.security_agent import SecurityAgent
        
        # Registra
        self.register_agent(GeneralAgent)
        self.register_agent(KnowledgeAgent)
        self.register_agent(MemoryAgent)
        self.register_agent(PlannerAgent)
        self.register_agent(HomeAutomationAgent)
        self.register_agent(InformationAgent)
        self.register_agent(LearningAgent)
        self.register_agent(SecurityAgent)
    
    def register_agent(self, agent_class: Type[BaseAgent]) -> bool:
        """
        Registra um agente.
        
        Args:
            agent_class: Classe do agente (deve herdar de BaseAgent)
            
        Returns:
            True se registrado com sucesso
        """
        try:
            # Cria instância
            agent = agent_class(
                event_bus=self.event_bus,
                logger=self.logger,
                config=self.config
            )
            
            # Inicializa
            asyncio.create_task(agent.initialize())
            
            # Armazena
            self._agents[agent.name] = agent
            self._agent_status[agent.name] = {
                "status": "registered",
                "capabilities": agent.capabilities,
                "task_count": 0
            }
            
            # Cria fila
            self._task_queues[agent.name] = asyncio.Queue()
            
            # Inicia worker
            self._queue_workers[agent.name] = asyncio.create_task(
                self._process_queue(agent.name)
            )
            
            self.logger.info(f"Agente registrado: {agent.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao registrar agente: {e}")
            return False
    
    async def _on_register(self, event: Event) -> None:
        """Registra um agente via evento."""
        payload = event.payload
        agent_class_path = payload.get("agent_class")
        
        if not agent_class_path:
            self.logger.error("Nenhuma classe de agente fornecida")
            return
        
        try:
            # Importa dinamicamente
            module_path, class_name = agent_class_path.rsplit(".", 1)
            module = __import__(module_path, fromlist=[class_name])
            agent_class = getattr(module, class_name)
            
            success = self.register_agent(agent_class)
            
            await self.event_bus.publish_async(
                "agent.registered",
                {
                    "success": success,
                    "agent_class": agent_class_path,
                    "timestamp": datetime.now().isoformat()
                },
                source="agent_manager"
            )
            
        except Exception as e:
            self.logger.error(f"Erro ao registrar agente via evento: {e}")
    
    # ===== SELEÇÃO =====
    
    async def _on_select(self, event: Event) -> None:
        """Seleciona um agente para uma tarefa."""
        payload = event.payload
        intent = payload.get("intent", "general")
        task = payload.get("task", {})
        request_id = payload.get("request_id")
        
        selected = self.select_agent(intent, task)
        
        if selected:
            await self.event_bus.publish_async(
                "agent.selected",
                {
                    "agent": selected,
                    "intent": intent,
                    "task": task,
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat()
                },
                source="agent_manager"
            )
        else:
            await self.event_bus.publish_async(
                "agent.no_agent_available",
                {
                    "intent": intent,
                    "task": task,
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat()
                },
                source="agent_manager"
            )
    
    def select_agent(self, intent: str, task: Dict[str, Any] = None) -> Optional[str]:
        """
        Seleciona o melhor agente para uma tarefa.
        
        Estratégia:
        1. Agentes especializados na intenção
        2. Agentes com capacidades correspondentes
        3. Agente geral (fallback)
        """
        # Mapeamento de intenção para agente
        intent_map = {
            "conversation": "general",
            "question": "knowledge",
            "command": "information",
            "planning": "planner",
            "learning": "learning",
            "emergency": "security",
            "memory": "memory",
            "home_automation": "home_automation",
            "information": "information"
        }
        
        preferred = intent_map.get(intent)
        
        if preferred and preferred in self._agents:
            agent = self._agents[preferred]
            if agent.can_handle(intent) and self._is_available(preferred):
                return preferred
        
        # Busca agente por capacidade
        for name, agent in self._agents.items():
            if agent.can_handle(intent) and self._is_available(name):
                return name
        
        # Fallback: general agent
        if "general" in self._agents and self._is_available("general"):
            return "general"
        
        # Qualquer agente disponível
        for name in self._agents.keys():
            if self._is_available(name):
                return name
        
        return None
    
    def _is_available(self, agent_name: str) -> bool:
        """Verifica se um agente está disponível."""
        status = self._agent_status.get(agent_name, {})
        return status.get("status") != "busy"
    
    # ===== ATRIBUIÇÃO =====
    
    async def _on_assign_task(self, event: Event) -> None:
        """Atribui uma tarefa a um agente."""
        payload = event.payload
        agent_name = payload.get("agent")
        task = payload.get("task")
        request_id = payload.get("request_id")
        
        if not agent_name or not task:
            await self._send_error("invalid_request", "Agente ou tarefa não fornecidos", request_id)
            return
        
        if agent_name not in self._task_queues:
            await self._send_error("agent_not_found", f"Agente {agent_name} não encontrado", request_id)
            return
        
        # Adiciona à fila
        await self._task_queues[agent_name].put({
            "task": task,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat()
        })
        
        # Atualiza status
        self._agent_status[agent_name]["status"] = "queued"
        
        self.logger.debug(f"Tarefa enfileirada para {agent_name}")
    
    async def _process_queue(self, agent_name: str) -> None:
        """Processa a fila de um agente."""
        queue = self._task_queues.get(agent_name)
        agent = self._agents.get(agent_name)
        
        if not queue or not agent:
            return
        
        while self._running:
            try:
                # Pega da fila
                item = await queue.get()
                
                # Atualiza status
                self._agent_status[agent_name]["status"] = "busy"
                
                # Processa
                try:
                    await agent.handle_event(
                        Event(
                            type=f"agent.{agent_name}",
                            payload=item,
                            source="agent_manager"
                        )
                    )
                    self._agent_status[agent_name]["task_count"] = \
                        self._agent_status[agent_name].get("task_count", 0) + 1
                except Exception as e:
                    self.logger.error(f"Erro processando tarefa em {agent_name}: {e}")
                
                # Atualiza status
                self._agent_status[agent_name]["status"] = "idle"
                
                queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Erro no worker de {agent_name}: {e}")
    
    # ===== EVENTOS DE AGENTES =====
    
    async def _on_agent_event(self, event: Event) -> None:
        """Roteia evento para o agente apropriado."""
        # Extrai o nome do agente do tipo do evento
        agent_name = event.type.replace("agent.", "")
        
        if agent_name in self._agents:
            # Coloca na fila do agente
            if agent_name in self._task_queues:
                await self._task_queues[agent_name].put({
                    "task": event.payload,
                    "source": event.source,
                    "timestamp": datetime.now().isoformat()
                })
        else:
            self.logger.warning(f"Agente não encontrado: {agent_name}")
    
    # ===== STATUS =====
    
    async def _on_get_status(self, event: Event) -> None:
        """Retorna status dos agentes."""
        request_id = event.payload.get("request_id")
        
        status = self.get_status()
        
        await self.event_bus.publish_async(
            "agent.status",
            {
                "status": status,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="agent_manager"
        )
    
    async def _on_list_agents(self, event: Event) -> None:
        """Lista agentes registrados."""
        request_id = event.payload.get("request_id")
        
        await self.event_bus.publish_async(
            "agent.list_result",
            {
                "agents": [
                    {
                        "name": name,
                        "capabilities": agent.capabilities,
                        "status": self._agent_status.get(name, {}).get("status", "unknown")
                    }
                    for name, agent in self._agents.items()
                ],
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="agent_manager"
        )
    
    # ===== MONITORAMENTO =====
    
    async def _monitor_agents(self) -> None:
        """Monitora a saúde dos agentes."""
        while self._running:
            try:
                await asyncio.sleep(self._monitor_interval)
                
                for name, agent in self._agents.items():
                    try:
                        health = await agent.health_check()
                        self._agent_status[name]["health"] = health
                    except Exception as e:
                        self.logger.error(f"Erro no health check de {name}: {e}")
                        self._agent_status[name]["health"] = {"error": str(e)}
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Erro no monitoramento: {e}")
    
    # ===== UTILITÁRIOS =====
    
    async def _send_error(self, code: str, message: str, request_id: Optional[str] = None) -> None:
        """Envia erro."""
        await self.event_bus.publish_async(
            "agent.error",
            {
                "code": code,
                "message": message,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="agent_manager"
        )
    
    # ===== MÉTODOS PÚBLICOS =====
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Obtém um agente pelo nome."""
        return self._agents.get(name)
    
    def get_status(self) -> Dict[str, Any]:
        """Obtém status de todos os agentes."""
        return {
            "total": len(self._agents),
            "agents": {
                name: {
                    "status": status.get("status", "unknown"),
                    "capabilities": agent.capabilities,
                    "task_count": status.get("task_count", 0),
                    "health": status.get("health", {})
                }
                for name, (agent, status) in zip(self._agents.keys(), self._agent_status.values())
            },
            "running": self._running
        }
    
    async def health_check(self) -> dict:
        """Health check do AgentManager."""
        return {
            "status": "running" if self._running else "stopped",
            "total_agents": len(self._agents),
            "active_agents": len([s for s in self._agent_status.values() if s.get("status") == "idle"])
        }