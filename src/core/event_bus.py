"""Barramento de eventos do Core EVA OS."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Union
from uuid import uuid4


class EventPriority(Enum):
    """Prioridade de eventos."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class Event:
    """Evento no barramento."""
    type: str
    data: Any = None
    source: str = "system"
    priority: EventPriority = EventPriority.NORMAL
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None
    
    def __post_init__(self):
        if isinstance(self.priority, int):
            self.priority = EventPriority(self.priority)
    
    @property
    def payload(self):
        """Compatibilidade com código antigo que usa event.payload."""
        return self.data


class EventBus:
    """
    Barramento de eventos central.
    Todo módulo conversa através dele.
    """
    
    def __init__(self, logger):
        self.logger = logger
        
        # ===== UMA ÚNICA LISTA DE LISTENERS =====
        self._listeners: Dict[str, List[Callable]] = {}
        
        # Fila para processamento assíncrono
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        
        # Histórico para debugging
        self._history: List[Event] = []
        self._max_history = 1000
    
    async def initialize(self) -> None:
        """Inicializa o barramento."""
        self._running = True
        self._worker_task = asyncio.create_task(self._process_events())
        self.logger.info("EventBus inicializado")
    
    # ===== REGISTRO DE LISTENERS =====
    
    def subscribe(self, event_type: str, callback: Callable) -> None:
        """
        Registra um listener.
        Aceita tanto funções síncronas quanto assíncronas.
        """
        if not callable(callback):
            raise ValueError(f"Callback para {event_type} não é callable")
        
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)
        
        is_async = asyncio.iscoroutinefunction(callback)
        self.logger.info(f"📋 [EventBus] Listener registrado: {event_type} (async={is_async}) - total: {len(self._listeners[event_type])}")
    
    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Remove um listener."""
        if event_type in self._listeners:
            try:
                self._listeners[event_type].remove(callback)
                self.logger.debug(f"Listener removido de: {event_type}")
            except ValueError:
                pass
    
    def has_subscribers(self, event_type: str) -> bool:
        """Verifica se há inscritos para um evento."""
        return event_type in self._listeners and len(self._listeners[event_type]) > 0
    
    def get_listeners_count(self, event_type: str) -> int:
        """Retorna o número de listeners para um evento."""
        return len(self._listeners.get(event_type, []))
    
    # ===== PUBLICAÇÃO =====
    
    def publish(self, event: Union[Event, str, Dict], data: Any = None, 
                source: str = "system", priority: EventPriority = EventPriority.NORMAL) -> None:
        """
        Publica um evento síncrono.
        """
        event = self._normalize_event(event, data, source, priority)
        
        self.logger.info(f"📤 [EventBus] publish: {event.type} de {event.source}")
        
        # Dispatch direto (síncrono)
        self._dispatch_sync(event)
        
        # Também coloca na fila para processamento assíncrono
        asyncio.create_task(self._queue.put(event))
        
        self._add_to_history(event)
    
    async def publish_async(self, event: Union[Event, str, Dict], data: Any = None,
                           source: str = "system", priority: EventPriority = EventPriority.NORMAL) -> None:
        """
        Publica um evento assíncrono.
        SOMENTE FILA - sem dispatch síncrono.
        """
        event = self._normalize_event(event, data, source, priority)
        
        self.logger.info(f"📤 [EventBus] publish_async: {event.type} de {event.source}")
        self.logger.info(f"📤 [EventBus] Listeners para '{event.type}': {self.get_listeners_count(event.type)}")
        
        # ===== SOMENTE FILA =====
        await self._queue.put(event)
        
        self._add_to_history(event)
    
    def _normalize_event(self, event, data, source, priority) -> Event:
        """Normaliza o evento para o formato padrão."""
        if isinstance(event, str):
            return Event(
                type=event,
                data=data,
                source=source,
                priority=priority
            )
        elif isinstance(event, dict):
            return Event(
                type=event.get("type", "unknown"),
                data=event.get("data"),
                source=event.get("source", "system"),
                priority=event.get("priority", EventPriority.NORMAL)
            )
        return event
    
    # ===== DISPATCH =====
    
    async def _process_events(self) -> None:
        """Processa eventos da fila assíncrona."""
        while self._running:
            try:
                event = await self._queue.get()
                self.logger.info(f"📥 [EventBus] Processando da fila: {event.type}")
                await self._dispatch_async(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Erro processando evento: {e}")
    
    def _dispatch_sync(self, event: Event) -> None:
        """Distribui evento para listeners síncronos."""
        listeners = self._listeners.get(event.type, [])
        self.logger.info(f"📨 [EventBus] _dispatch_sync: {event.type} -> {len(listeners)} listeners")
        
        for callback in listeners:
            try:
                if asyncio.iscoroutinefunction(callback):
                    # Cria task para não bloquear
                    asyncio.create_task(callback(event))
                    self.logger.info(f"📨 [EventBus] Async task criada para {callback.__name__}")
                else:
                    callback(event)
                    self.logger.info(f"📨 [EventBus] Sync callback executado: {callback.__name__}")
            except Exception as e:
                self.logger.error(f"Erro no listener {callback.__name__}: {e}")
        
        # Wildcard
        if "*" in self._listeners:
            for callback in self._listeners["*"]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(event))
                    else:
                        callback(event)
                except Exception as e:
                    self.logger.error(f"Erro no listener wildcard: {e}")
    
    async def _dispatch_async(self, event: Event) -> None:
        """Distribui evento para listeners assíncronos."""
        listeners = self._listeners.get(event.type, [])
        self.logger.info(f"📨 [EventBus] _dispatch_async: {event.type} -> {len(listeners)} listeners")
        
        for callback in listeners:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                    self.logger.info(f"📨 [EventBus] Async callback executado: {callback.__name__}")
                else:
                    callback(event)
                    self.logger.info(f"📨 [EventBus] Sync callback executado: {callback.__name__}")
            except Exception as e:
                self.logger.error(f"Erro no async listener {callback.__name__}: {e}")
        
        # Wildcard
        if "*" in self._listeners:
            for callback in self._listeners["*"]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    self.logger.error(f"Erro no async listener wildcard: {e}")
    
    # ===== UTILITÁRIOS =====
    
    def _add_to_history(self, event: Event) -> None:
        """Adiciona evento ao histórico."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
    
    def get_history(self, limit: int = 100, event_type: Optional[str] = None) -> List[Event]:
        """Obtém histórico de eventos."""
        if event_type:
            filtered = [e for e in self._history if e.type == event_type]
            return filtered[-limit:]
        return self._history[-limit:]
    
    def clear_history(self) -> None:
        """Limpa histórico."""
        self._history.clear()
    
    def clear(self) -> None:
        """Limpa todos os listeners."""
        self._listeners.clear()
        self.logger.info("EventBus limpo")
    
    async def shutdown(self) -> None:
        """Desliga o barramento."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self.logger.info("EventBus desligado")