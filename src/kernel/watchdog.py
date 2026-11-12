"""Watchdog - Guardião da EVA."""

import asyncio
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
import traceback


@dataclass
class ModuleHeartbeat:
    """Heartbeat de um módulo."""
    module_name: str
    last_heartbeat: datetime = field(default_factory=datetime.now)
    status: str = "alive"  # alive, warning, dead
    errors: List[str] = field(default_factory=list)
    consecutive_failures: int = 0


class Watchdog:
    """
    Guardião da EVA.
    Detecta travamentos, reinicia módulos, verifica recursos.
    Nunca deixa a EVA morrer.
    """
    
    def __init__(self, logger, event_bus, config):
        self.logger = logger
        self.event_bus = event_bus
        self.config = config
        
        self._heartbeats: Dict[str, ModuleHeartbeat] = {}
        self._running = False
        self._watchdog_task: Optional[asyncio.Task] = None
        
        # Configurações
        self._heartbeat_timeout = 30  # segundos
        self._check_interval = 5  # segundos
        self._max_consecutive_failures = 3
        
        # Limites de recursos
        self._resource_limits = {
            "cpu": config.get("resources.max_cpu_percent", 80),
            "ram": config.get("resources.max_ram_percent", 85),
            "disk": config.get("resources.max_disk_percent", 90)
        }
        
        # Módulos registrados com suas funções de reinício
        self._restart_handlers: Dict[str, callable] = {}
        
        # Histórico de alertas
        self._alerts: List[Dict[str, Any]] = []
        self._max_alerts = 100
    
    async def initialize(self) -> None:
        """Inicializa o watchdog."""
        self._running = True
        self._watchdog_task = asyncio.create_task(self._run_watchdog())
        self.logger.info("Watchdog inicializado")
    
    def register_module(self, module_name: str, restart_handler: callable = None) -> None:
        """Registra um módulo para monitoramento."""
        if module_name not in self._heartbeats:
            self._heartbeats[module_name] = ModuleHeartbeat(module_name)
            self.logger.info(f"Módulo registrado no Watchdog: {module_name}")
        
        if restart_handler:
            self._restart_handlers[module_name] = restart_handler
    
    def heartbeat(self, module_name: str) -> None:
        """
        Recebe um heartbeat de um módulo.
        Módulos devem chamar isso periodicamente.
        """
        if module_name in self._heartbeats:
            hb = self._heartbeats[module_name]
            hb.last_heartbeat = datetime.now()
            hb.status = "alive"
            hb.consecutive_failures = 0
            hb.errors.clear()
        else:
            # Registra automaticamente
            self.register_module(module_name)
            self._heartbeats[module_name].last_heartbeat = datetime.now()
    
    def report_error(self, module_name: str, error: str) -> None:
        """Reporta um erro de um módulo."""
        if module_name in self._heartbeats:
            hb = self._heartbeats[module_name]
            hb.errors.append(error)
            if len(hb.errors) > 10:
                hb.errors = hb.errors[-10:]
            
            hb.consecutive_failures += 1
            
            if hb.consecutive_failures >= self._max_consecutive_failures:
                hb.status = "dead"
                self.logger.error(f"Módulo {module_name} considerado morto ({hb.consecutive_failures} falhas)")
                asyncio.create_task(self._handle_dead_module(module_name))
    
    async def _run_watchdog(self) -> None:
        """Loop principal do watchdog."""
        while self._running:
            try:
                now = datetime.now()
                
                # 1. Verifica heartbeats
                for module_name, hb in self._heartbeats.items():
                    if hb.status == "dead":
                        continue
                    
                    time_since = (now - hb.last_heartbeat).total_seconds()
                    if time_since > self._heartbeat_timeout:
                        hb.consecutive_failures += 1
                        if hb.consecutive_failures >= self._max_consecutive_failures:
                            hb.status = "dead"
                            self.logger.error(f"Watchdog: Módulo {module_name} falhou (sem heartbeat por {time_since:.1f}s)")
                            await self._handle_dead_module(module_name)
                        else:
                            hb.status = "warning"
                            self.logger.warning(f"Watchdog: Módulo {module_name} com heartbeat atrasado ({time_since:.1f}s)")
                
                # 2. Verifica recursos do sistema
                await self._check_system_resources()
                
                # 3. Verifica se o watchdog está vivo
                await self._check_watchdog_health()
                
                await asyncio.sleep(self._check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Erro no watchdog: {e}")
                await asyncio.sleep(10)
    
    async def _check_system_resources(self) -> None:
        """Verifica recursos do sistema."""
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            
            alerts = []
            
            if cpu > self._resource_limits["cpu"]:
                alerts.append(f"CPU alta: {cpu}%")
                await self._publish_alert("resource_cpu", {"percent": cpu, "limit": self._resource_limits["cpu"]})
            
            if ram > self._resource_limits["ram"]:
                alerts.append(f"RAM alta: {ram}%")
                await self._publish_alert("resource_ram", {"percent": ram, "limit": self._resource_limits["ram"]})
            
            if disk > self._resource_limits["disk"]:
                alerts.append(f"Disco alto: {disk}%")
                await self._publish_alert("resource_disk", {"percent": disk, "limit": self._resource_limits["disk"]})
            
            if alerts:
                self.logger.warning(f"Recursos: {', '.join(alerts)}")
                
        except Exception as e:
            self.logger.error(f"Erro ao verificar recursos: {e}")
    
    async def _check_watchdog_health(self) -> None:
        """Verifica se o próprio watchdog está saudável."""
        # Publica heartbeat do watchdog
        await self.event_bus.publish_async(
            "WATCHDOG_HEARTBEAT",
            {
                "timestamp": datetime.now().isoformat(),
                "modules": len(self._heartbeats),
                "alive": sum(1 for hb in self._heartbeats.values() if hb.status == "alive"),
                "dead": sum(1 for hb in self._heartbeats.values() if hb.status == "dead")
            },
            source="watchdog"
        )
    
    async def _handle_dead_module(self, module_name: str) -> None:
        """Tenta recuperar um módulo morto."""
        self.logger.info(f"Tentando recuperar módulo: {module_name}")
        
        # Publica evento
        await self.event_bus.publish_async(
            "WATCHDOG_MODULE_DEAD",
            {
                "module": module_name,
                "timestamp": datetime.now().isoformat()
            },
            source="watchdog"
        )
        
        # Tenta reiniciar
        if module_name in self._restart_handlers:
            try:
                handler = self._restart_handlers[module_name]
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
                
                # Aguarda recuperação
                await asyncio.sleep(5)
                
                # Verifica se recuperou
                if module_name in self._heartbeats:
                    hb = self._heartbeats[module_name]
                    if hb.status == "alive":
                        self.logger.info(f"Módulo {module_name} recuperado com sucesso")
                        await self._publish_alert("module_recovered", {"module": module_name})
                        return
                
                self.logger.error(f"Falha ao recuperar módulo {module_name}")
                
            except Exception as e:
                self.logger.error(f"Erro ao reiniciar {module_name}: {e}")
        else:
            self.logger.warning(f"Nenhum handler de reinício para {module_name}")
        
        # Módulo permanece morto
        await self._publish_alert("module_dead", {"module": module_name})
    
    async def _publish_alert(self, alert_type: str, data: Dict[str, Any]) -> None:
        """Publica um alerta."""
        alert = {
            "type": alert_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        self._alerts.append(alert)
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]
        
        await self.event_bus.publish_async(
            "WATCHDOG_ALERT",
            alert,
            source="watchdog"
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Obtém status atual."""
        now = datetime.now()
        
        return {
            "running": self._running,
            "modules": {
                name: {
                    "status": hb.status,
                    "last_heartbeat": hb.last_heartbeat.isoformat(),
                    "seconds_since": (now - hb.last_heartbeat).total_seconds(),
                    "errors": hb.errors[-5:],
                    "consecutive_failures": hb.consecutive_failures
                }
                for name, hb in self._heartbeats.items()
            },
            "alerts": self._alerts[-10:],
            "resource_limits": self._resource_limits
        }
    
    def get_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Obtém alertas recentes."""
        return self._alerts[-limit:]
    
    def set_heartbeat_timeout(self, seconds: int) -> None:
        """Define o timeout de heartbeat."""
        self._heartbeat_timeout = seconds
        self.logger.info(f"Heartbeat timeout: {seconds}s")
    
    async def shutdown(self) -> None:
        """Desliga o watchdog."""
        self._running = False
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Watchdog desligado")