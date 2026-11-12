"""Gerenciador de interfaces da EVA."""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.kernel.events import Event, EventBus


class InterfaceManager:
    """
    Gerenciador de interfaces da EVA.
    
    Responsabilidades:
    - Orquestrar todas as interfaces
    - Gerenciar ciclo de vida das interfaces
    - Rotear mensagens entre interfaces
    - Monitorar conexões
    """
    
    __plugin_name__ = "interface_manager"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Gerenciador de interfaces da EVA"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["core", "interfaces", "communication"]
    __plugin_capabilities__ = ["interface_management"]
    __plugin_requires__ = ["event_bus", "logger", "config"]
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        # Interfaces ativas
        self._interfaces: Dict[str, Any] = {}
        self._interface_status: Dict[str, Dict[str, Any]] = {}
        
        # Conexões ativas
        self._connections: Dict[str, Dict[str, Any]] = {}
        
        # Estado
        self._running = False
        
        # Registra listeners
        self._register_listeners()
        
        self.logger.info("InterfaceManager inicializado")
    
    def _register_listeners(self) -> None:
        """Registra ouvintes de eventos."""
        self.event_bus.subscribe("interface.register", self._on_register)
        self.event_bus.subscribe("interface.start", self._on_start)
        self.event_bus.subscribe("interface.stop", self._on_stop)
        self.event_bus.subscribe("interface.status", self._on_status)
        self.event_bus.subscribe("interface.message", self._on_message)
    
    async def initialize(self) -> None:
        """Inicializa o InterfaceManager."""
        self.logger.info("InterfaceManager inicializando...")
        self._running = True
        self.logger.info("InterfaceManager inicializado")
    
    async def start(self) -> None:
        """Inicia o InterfaceManager."""
        self.logger.info("InterfaceManager iniciando...")
        
        # Inicia CLI
        await self._start_cli()
        
        # Inicia API
        await self._start_api()
        
        self.logger.info("InterfaceManager pronto")
    
    async def shutdown(self) -> None:
        """Desliga o InterfaceManager."""
        self.logger.info("InterfaceManager desligando...")
        self._running = False
        
        # Para interfaces
        for name, interface in self._interfaces.items():
            if hasattr(interface, "shutdown"):
                try:
                    await interface.shutdown()
                except Exception as e:
                    self.logger.error(f"Erro ao desligar {name}: {e}")
        
        self.logger.info("InterfaceManager desligado")
    
    # ===== COMANDOS =====
    
    async def _on_register(self, event: Event) -> None:
        """Registra uma interface."""
        payload = event.payload
        name = payload.get("name")
        interface = payload.get("interface")
        
        if name in self._interfaces:
            self.logger.warning(f"Interface {name} já registrada")
            return
        
        self._interfaces[name] = interface
        self._interface_status[name] = {
            "status": "registered",
            "registered_at": datetime.now().isoformat()
        }
        
        self.logger.info(f"Interface registrada: {name}")
        
        await self.event_bus.publish_async(
            "interface.registered",
            {
                "name": name,
                "timestamp": datetime.now().isoformat()
            },
            source="interface_manager"
        )
    
    async def _on_start(self, event: Event) -> None:
        """Inicia uma interface."""
        payload = event.payload
        name = payload.get("name")
        
        if name not in self._interfaces:
            self.logger.warning(f"Interface {name} não encontrada")
            return
        
        interface = self._interfaces[name]
        
        if hasattr(interface, "start"):
            try:
                await interface.start()
                self._interface_status[name]["status"] = "running"
                self._interface_status[name]["started_at"] = datetime.now().isoformat()
                self.logger.info(f"Interface iniciada: {name}")
            except Exception as e:
                self.logger.error(f"Erro ao iniciar {name}: {e}")
                self._interface_status[name]["status"] = "error"
                self._interface_status[name]["error"] = str(e)
    
    async def _on_stop(self, event: Event) -> None:
        """Para uma interface."""
        payload = event.payload
        name = payload.get("name")
        
        if name not in self._interfaces:
            return
        
        interface = self._interfaces[name]
        
        if hasattr(interface, "shutdown"):
            try:
                await interface.shutdown()
                self._interface_status[name]["status"] = "stopped"
                self.logger.info(f"Interface parada: {name}")
            except Exception as e:
                self.logger.error(f"Erro ao parar {name}: {e}")
    
    async def _on_status(self, event: Event) -> None:
        """Retorna status das interfaces."""
        request_id = event.payload.get("request_id")
        
        await self.event_bus.publish_async(
            "interface.status_result",
            {
                "interfaces": self._interface_status,
                "connections": len(self._connections),
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="interface_manager"
        )
    
    async def _on_message(self, event: Event) -> None:
        """Processa mensagem de uma interface."""
        payload = event.payload
        source = payload.get("source", "unknown")
        message = payload.get("message", "")
        data = payload.get("data", {})
        
        self.logger.debug(f"Mensagem de {source}: {message[:50]}...")
        
        # Publica para o sistema
        await self.event_bus.publish_async(
            "user.message",
            {
                "text": message,
                "source": source,
                "data": data,
                "timestamp": datetime.now().isoformat()
            },
            source="interface_manager"
        )
    
    # ===== INTERFACES INTERNAS =====
    
    async def _start_cli(self) -> None:
        """Inicia a interface CLI."""
        try:
            from src.interfaces.cli.cli import CLI
            cli = CLI(self.event_bus, self.logger, self.config)
            await cli.initialize()
            self._interfaces["cli"] = cli
            self._interface_status["cli"] = {
                "status": "registered",
                "registered_at": datetime.now().isoformat()
            }
            self.logger.info("CLI registrada")
        except Exception as e:
            self.logger.error(f"Erro ao iniciar CLI: {e}")
    
    async def _start_api(self) -> None:
        """Inicia a interface API."""
        try:
            from src.interfaces.api.app import APIApp
            api = APIApp(self.event_bus, self.logger, self.config)
            await api.initialize()
            self._interfaces["api"] = api
            self._interface_status["api"] = {
                "status": "registered",
                "registered_at": datetime.now().isoformat()
            }
            self.logger.info("API registrada")
        except Exception as e:
            self.logger.error(f"Erro ao iniciar API: {e}")
    
    # ===== MÉTODOS PÚBLICOS =====
    
    def get_interface(self, name: str) -> Optional[Any]:
        """Obtém uma interface pelo nome."""
        return self._interfaces.get(name)
    
    def get_status(self) -> Dict[str, Any]:
        """Obtém status de todas as interfaces."""
        return {
            "interfaces": self._interface_status,
            "total": len(self._interfaces),
            "running": self._running
        }
    
    async def health_check(self) -> dict:
        """Health check do InterfaceManager."""
        return {
            "status": "running" if self._running else "stopped",
            "total_interfaces": len(self._interfaces),
            "active_interfaces": len([
                s for s in self._interface_status.values()
                if s.get("status") == "running"
            ])
        }