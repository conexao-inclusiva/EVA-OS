"""Barramento de eventos do EVA OS."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4


class EventPriority(Enum):
    """Prioridades para eventos."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class Event:
    """Evento no barramento do sistema."""
    type: str
    payload: Any
    source: str
    priority: EventPriority = EventPriority.NORMAL
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None

    @property
    def data(self) -> Any:
        """Compatibilidade com consumidores que usam event.data."""
        return self.payload


class EventBus:
    """Barramento de eventos desacoplado."""
    
    def __init__(self, logger):
        self.logger = logger
        self._listeners: Dict[str, List[Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
    
    async def initialize(self) -> None:
        """Inicia o barramento."""
        self._running = True
        self._worker_task = asyncio.create_task(self._process_events())
        self.logger.info("EventBus inicializado")
    
    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Registra um ouvinte para um tipo de evento."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)
        self.logger.debug(f"Listener registrado para: {event_type}")
    
    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Remove um ouvinte."""
        if event_type in self._listeners:
            self._listeners[event_type].remove(callback)
    
    async def publish(self, event: Event) -> None:
        """Publica um evento no barramento."""
        await self._queue.put(event)
        self.logger.debug(f"Evento publicado: {event.type} de {event.source}")
    
    async def publish_async(self, event_name: str, data: Dict[str, Any], source: Optional[str] = None) -> None:
        """Publica evento no formato usado pelo Brain e VoiceManager."""
        await self.publish(Event(type=event_name, payload=data, source=source or "unknown"))

    async def _process_events(self) -> None:
        """Processa eventos em fila."""
        while self._running:
            try:
                event = await self._queue.get()
                await self._dispatch(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Erro processando evento: {e}")
    
    async def _dispatch(self, event: Event) -> None:
        """Distribui evento para todos os ouvintes."""
        if event.type in self._listeners:
            for callback in self._listeners[event.type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    self.logger.error(f"Erro no listener {callback}: {e}")
    
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