"""Gerenciador central da Consciência da EVA."""

import asyncio
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from enum import Enum

from src.kernel.events import Event, EventBus
from src.consciousness.decision_engine import DecisionEngine
from src.consciousness.intent_classifier import IntentClassifier
from src.consciousness.intent_router import IntentRouter
from src.consciousness.context_analyzer import ContextAnalyzer
from src.consciousness.priority_arbiter import PriorityArbiter
from src.consciousness.reflection_engine import ReflectionEngine
from src.consciousness.state_orchestrator import StateOrchestrator


class ConsciousnessState(Enum):
    """Estados da Consciência."""
    IDLE = "idle"
    ANALYZING = "analyzing"
    DECIDING = "deciding"
    ROUTING = "routing"
    REFLECTING = "reflecting"
    LEARNING = "learning"


class ConsciousnessManager:
    """
    Gerenciador central da Consciência da EVA.
    
    Responsabilidades:
    - Receber e analisar eventos
    - Classificar intenções
    - Analisar contexto
    - Tomar decisões
    - Rotear para agentes/planners
    - Refletir sobre ações passadas
    - Orquestrar estados do sistema
    """
    
    # Atributos de plugin
    __plugin_name__ = "consciousness_manager"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Centro de decisão da EVA"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["core", "consciousness", "intelligence"]
    __plugin_capabilities__ = ["decision_making", "intent_recognition", "orchestration"]
    __plugin_requires__ = ["event_bus", "logger", "config", "context_manager", "planner_manager"]
    
    def __init__(self, event_bus: EventBus, logger, config, context_manager, planner_manager):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self.context_manager = context_manager
        self.planner_manager = planner_manager
        
        # Inicializa componentes
        self.decision_engine = DecisionEngine(self)
        self.intent_classifier = IntentClassifier(self)
        self.intent_router = IntentRouter(self)
        self.context_analyzer = ContextAnalyzer(self)
        self.priority_arbiter = PriorityArbiter(self)
        self.reflection_engine = ReflectionEngine(self)
        self.state_orchestrator = StateOrchestrator(self)
        
        # Estado interno
        self._state = ConsciousnessState.IDLE
        self._last_decision: Optional[Dict[str, Any]] = None
        self._decision_history: List[Dict[str, Any]] = []
        self._running = False
        self._reflection_task: Optional[asyncio.Task] = None
        self._reflection_interval = 3600  # 1 hora
        
        # Registra listeners
        self._register_listeners()
        
        self.logger.info("ConsciousnessManager inicializado")
    
    def _register_listeners(self) -> None:
        """Registra ouvintes de eventos."""
        # Eventos de entrada
        self.event_bus.subscribe("user.message", self._on_user_message)
        self.event_bus.subscribe("voice.input", self._on_voice_input)
        self.event_bus.subscribe("command", self._on_command)
        self.event_bus.subscribe("system.event", self._on_system_event)
        self.event_bus.subscribe("sensor.trigger", self._on_sensor_trigger)
        
        # Eventos internos
        self.event_bus.subscribe("consciousness.decide", self._on_decide)
        self.event_bus.subscribe("consciousness.reflect", self._on_reflect)
        self.event_bus.subscribe("consciousness.get_status", self._on_get_status)
        
        # Eventos de resultado
        self.event_bus.subscribe("plan.completed", self._on_plan_completed)
        self.event_bus.subscribe("task.completed", self._on_task_completed)
        self.event_bus.subscribe("agent.response", self._on_agent_response)
    
    async def initialize(self) -> None:
        """Inicializa a Consciência."""
        self.logger.info("ConsciousnessManager inicializando...")
        
        self._running = True
        
        # Inicia reflexão periódica
        self._reflection_task = asyncio.create_task(self._auto_reflect())
        
        self.logger.info("ConsciousnessManager inicializado")
    
    async def start(self) -> None:
        """Inicia a Consciência."""
        self.logger.info("ConsciousnessManager iniciando...")
        
        # Publica que a consciência está pronta
        await self.event_bus.publish_async(
            "CONSCIOUSNESS_READY",
            {
                "timestamp": datetime.now().isoformat(),
                "state": self._state.value
            },
            source="consciousness_manager"
        )
        
        self.logger.info("ConsciousnessManager pronto")
    
    async def shutdown(self) -> None:
        """Desliga a Consciência."""
        self.logger.info("ConsciousnessManager desligando...")
        
        self._running = False
        
        if self._reflection_task:
            self._reflection_task.cancel()
            try:
                await self._reflection_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("ConsciousnessManager desligado")
    
    # ===== EVENTOS DE ENTRADA =====
    
    async def _on_user_message(self, event: Event) -> None:
        """Processa mensagem do usuário."""
        self.logger.debug(f"Mensagem do usuário: {event.payload.get('text', '')[:50]}...")
        self._set_state(ConsciousnessState.ANALYZING)
        
        # 1. Analisa contexto
        context = await self.context_analyzer.analyze(event)
        
        # 2. Classifica intenção
        intent = await self.intent_classifier.classify(event.payload.get("text", ""), context)
        
        # 3. Toma decisão
        decision = await self.decision_engine.decide(intent, context, event)
        
        # 4. Roteia para o destino apropriado
        await self.intent_router.route(decision, context)
        
        # 5. Registra decisão
        self._record_decision(decision, context)
        
        self._set_state(ConsciousnessState.IDLE)
    
    async def _on_voice_input(self, event: Event) -> None:
        """Processa entrada de voz."""
        # Converte para mensagem de usuário
        text = event.payload.get("text", "")
        await self._on_user_message(
            Event(
                type="user.message",
                payload={"text": text, "source": "voice", "user": event.payload.get("user")},
                source=event.source
            )
        )
    
    async def _on_command(self, event: Event) -> None:
        """Processa comando direto."""
        self.logger.debug(f"Comando recebido: {event.payload.get('command', '')}")
        self._set_state(ConsciousnessState.ANALYZING)
        
        # Comandos são de alta prioridade
        command = event.payload.get("command", "")
        params = event.payload.get("params", {})
        
        # Tenta executar diretamente se for um comando do sistema
        if command.startswith("system."):
            await self._handle_system_command(command, params)
        else:
            # Trata como mensagem de usuário com intenção de comando
            await self._on_user_message(
                Event(
                    type="user.message",
                    payload={
                        "text": command,
                        "params": params,
                        "user": event.payload.get("user", "system")
                    },
                    source=event.source
                )
            )
        
        self._set_state(ConsciousnessState.IDLE)
    
    async def _on_system_event(self, event: Event) -> None:
        """Processa evento do sistema."""
        event_type = event.payload.get("event_type", "unknown")
        
        # Eventos importantes podem exigir decisão
        if event_type in ["error", "warning", "critical"]:
            await self._handle_critical_event(event)
    
    async def _on_sensor_trigger(self, event: Event) -> None:
        """Processa trigger de sensor."""
        sensor_id = event.payload.get("sensor_id", "unknown")
        value = event.payload.get("value")
        
        self.logger.debug(f"Sensor {sensor_id}: {value}")
        
        # Verifica se requer ação
        if self._requires_action(sensor_id, value):
            await self._on_system_event(
                Event(
                    type="system.event",
                    payload={
                        "event_type": "sensor_trigger",
                        "sensor_id": sensor_id,
                        "value": value
                    },
                    source="consciousness_manager"
                )
            )
    
    # ===== EVENTOS INTERNOS =====
    
    async def _on_decide(self, event: Event) -> None:
        """Solicitação de decisão."""
        self._set_state(ConsciousnessState.DECIDING)
        
        payload = event.payload
        intent = payload.get("intent")
        context = payload.get("context", {})
        
        decision = await self.decision_engine.decide(intent, context, event)
        
        await self.event_bus.publish_async(
            "consciousness.decision_made",
            {
                "decision": decision,
                "timestamp": datetime.now().isoformat()
            },
            source="consciousness_manager"
        )
        
        self._set_state(ConsciousnessState.IDLE)
    
    async def _on_reflect(self, event: Event) -> None:
        """Solicitação de reflexão."""
        await self.reflection_engine.reflect()
    
    async def _on_get_status(self, event: Event) -> None:
        """Retorna status da Consciência."""
        await self.event_bus.publish_async(
            "consciousness.status",
            {
                "state": self._state.value,
                "last_decision": self._last_decision,
                "decision_count": len(self._decision_history),
                "timestamp": datetime.now().isoformat()
            },
            source="consciousness_manager"
        )
    
    # ===== EVENTOS DE RESULTADO =====
    
    async def _on_plan_completed(self, event: Event) -> None:
        """Processa conclusão de plano."""
        self.logger.info(f"Plano concluído: {event.payload.get('plan_id', '')[:8]}")
        
        # Registra aprendizado
        await self.reflection_engine.learn_from_plan(event.payload)
    
    async def _on_task_completed(self, event: Event) -> None:
        """Processa conclusão de tarefa."""
        self.logger.debug(f"Tarefa concluída: {event.payload.get('task_id', '')[:8]}")
    
    async def _on_agent_response(self, event: Event) -> None:
        """Processa resposta de agente."""
        # Pode gerar reflexão se necessário
        pass
    
    # ===== MÉTODOS AUXILIARES =====
    
    def _set_state(self, state: ConsciousnessState) -> None:
        """Define o estado da consciência."""
        old_state = self._state
        self._state = state
        
        if old_state != state:
            self.logger.debug(f"Estado da consciência: {old_state.value} -> {state.value}")
    
    def _record_decision(self, decision: Dict[str, Any], context: Dict[str, Any]) -> None:
        """Registra uma decisão."""
        self._last_decision = decision
        self._decision_history.append({
            "decision": decision,
            "context": context,
            "timestamp": datetime.now().isoformat()
        })
        
        # Limita histórico
        if len(self._decision_history) > 1000:
            self._decision_history = self._decision_history[-1000:]
    
    def _requires_action(self, sensor_id: str, value: Any) -> bool:
        """Verifica se um sensor requer ação."""
        # TODO: Implementar lógica de decisão para sensores
        return False
    
    async def _handle_system_command(self, command: str, params: Dict[str, Any]) -> None:
        """Manipula comandos do sistema."""
        if command == "system.shutdown":
            await self.event_bus.publish_async(
                "system.shutdown",
                params,
                source="consciousness_manager"
            )
        elif command == "system.restart":
            await self.event_bus.publish_async(
                "system.restart",
                params,
                source="consciousness_manager"
            )
        elif command == "system.status":
            await self.event_bus.publish_async(
                "system.status.request",
                params,
                source="consciousness_manager"
            )
        else:
            self.logger.warning(f"Comando desconhecido: {command}")
    
    async def _handle_critical_event(self, event: Event) -> None:
        """Manipula eventos críticos."""
        # Toma decisão imediata
        decision = await self.decision_engine.decide_emergency(event)
        
        if decision:
            await self.intent_router.route(decision, {})
    
    # ===== REFLEXÃO AUTOMÁTICA =====
    
    async def _auto_reflect(self) -> None:
        """Executa reflexão periódica."""
        while self._running:
            try:
                await asyncio.sleep(self._reflection_interval)
                
                if self._running:
                    self._set_state(ConsciousnessState.REFLECTING)
                    await self.reflection_engine.reflect()
                    self._set_state(ConsciousnessState.IDLE)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Erro na reflexão automática: {e}")
    
    # ===== MÉTODOS PÚBLICOS =====
    
    def get_state(self) -> ConsciousnessState:
        """Obtém o estado atual."""
        return self._state
    
    def get_last_decision(self) -> Optional[Dict[str, Any]]:
        """Obtém a última decisão."""
        return self._last_decision
    
    def get_decision_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtém histórico de decisões."""
        return self._decision_history[-limit:]
    
    async def health_check(self) -> dict:
        """Health check da Consciência."""
        return {
            "status": "running" if self._running else "stopped",
            "state": self._state.value,
            "decisions_made": len(self._decision_history),
            "last_decision": self._last_decision
        }