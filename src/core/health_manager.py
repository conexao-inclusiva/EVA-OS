"""Gerenciador de saúde do sistema."""

import asyncio
import psutil
import platform
from typing import Dict, Any, List, Optional
from datetime import datetime


class HealthManager:
    def __init__(self, logger, event_bus, config):
        self.logger = logger
        self.event_bus = event_bus
        self.config = config
        
        self._is_running = False
        self._check_task: Optional[asyncio.Task] = None
        self._interval = 60
        self._check_counter = 0
        
        self._last_status: Dict[str, Any] = {}
        self._history: List[Dict[str, Any]] = []
        self._max_history = 1000
        self._alerts: List[Dict[str, Any]] = []
        self._thresholds = {"cpu": 80.0, "ram": 85.0, "disk": 90.0, "response_time": 2.0}
        self._modules: Dict[str, Dict[str, Any]] = {}
        self._external_services: Dict[str, Dict[str, Any]] = {}
    
    async def initialize(self) -> None:
        self._is_running = True
        self._check_task = asyncio.create_task(self._periodic_check())
        self.logger.info("HealthManager inicializado")
    
    async def _periodic_check(self) -> None:
        while self._is_running:
            try:
                self._check_counter += 1
                if self._check_counter >= self._interval:
                    self._check_counter = 0
                    status = await self.check()
                    await self.event_bus.publish_async("HEALTH_STATUS", status, source="health_manager")
                    await self._check_alerts(status)
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                self.logger.debug("HealthManager: loop cancelado")
                break
            except Exception as e:
                self.logger.error(f"Erro no health check: {e}")
                await asyncio.sleep(1)
        self.logger.debug("HealthManager: loop finalizado")
    
    async def check(self) -> Dict[str, Any]:
        status = {
            "timestamp": datetime.now().isoformat(),
            "system": {"platform": platform.platform(), "python": platform.python_version()},
            "cpu": self._check_cpu(),
            "ram": self._check_ram(),
            "disk": self._check_disk(),
            "modules": await self._check_modules(),
            "external": await self._check_external_services()
        }
        self._last_status = status
        self._add_history(status)
        return status
    
    def _check_cpu(self) -> Dict[str, Any]:
        try:
            cpu_percent = psutil.cpu_percent(interval=0.5)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            return {
                "percent": cpu_percent,
                "count": cpu_count,
                "freq_current": cpu_freq.current if cpu_freq else 0,
                "freq_max": cpu_freq.max if cpu_freq else 0,
                "warning": cpu_percent > self._thresholds["cpu"]
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _check_ram(self) -> Dict[str, Any]:
        try:
            memory = psutil.virtual_memory()
            return {
                "percent": memory.percent,
                "total_gb": memory.total / (1024 ** 3),
                "available_gb": memory.available / (1024 ** 3),
                "used_gb": memory.used / (1024 ** 3),
                "warning": memory.percent > self._thresholds["ram"]
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _check_disk(self) -> Dict[str, Any]:
        try:
            disk = psutil.disk_usage('/')
            return {
                "percent": disk.percent,
                "total_gb": disk.total / (1024 ** 3),
                "used_gb": disk.used / (1024 ** 3),
                "free_gb": disk.free / (1024 ** 3),
                "warning": disk.percent > self._thresholds["disk"]
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _check_modules(self) -> Dict[str, Any]:
        status = {}
        for name, info in self._modules.items():
            try:
                module = info.get("instance")
                if module and hasattr(module, "health_check"):
                    if asyncio.iscoroutinefunction(module.health_check):
                        result = await module.health_check()
                    else:
                        result = module.health_check()
                    status[name] = result
                else:
                    status[name] = {"status": "unknown"}
            except Exception as e:
                status[name] = {"status": "error", "error": str(e)}
        return status
    
    async def _check_external_services(self) -> Dict[str, Any]:
        status = {}
        for name, config in self._external_services.items():
            status[name] = await self._check_external(name, config)
        return status
    
    async def _check_external(self, name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        service_type = config.get("type", "unknown")
        timeout = config.get("timeout", 2.0)
        if service_type == "ping":
            return await self._ping_service(name, config.get("host"), timeout)
        elif service_type == "http":
            return await self._http_service(config.get("url"), timeout)
        elif service_type == "tcp":
            return await self._tcp_service(config.get("host"), config.get("port"), timeout)
        else:
            return {"status": "unknown", "error": f"Tipo desconhecido: {service_type}"}
    
    async def _ping_service(self, name: str, host: str, timeout: float) -> Dict[str, Any]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", str(int(timeout)), host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return {"status": "online", "response_time": 0.001}
            else:
                return {"status": "offline", "error": stderr.decode().strip()}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _http_service(self, url: str, timeout: float) -> Dict[str, Any]:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    return {"status": "online", "status_code": response.status, "response_time": timeout}
        except Exception as e:
            return {"status": "offline", "error": str(e)}
    
    async def _tcp_service(self, host: str, port: int, timeout: float) -> Dict[str, Any]:
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                return {"status": "online"}
            else:
                return {"status": "offline", "error": f"Conexão recusada (código {result})"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _check_alerts(self, status: Dict[str, Any]) -> None:
        alerts = []
        cpu = status.get("cpu", {})
        if cpu.get("warning", False):
            alerts.append({"level": "warning", "component": "cpu", "message": f"CPU alta: {cpu.get('percent')}%", "threshold": self._thresholds["cpu"]})
        ram = status.get("ram", {})
        if ram.get("warning", False):
            alerts.append({"level": "warning", "component": "ram", "message": f"RAM alta: {ram.get('percent')}%", "threshold": self._thresholds["ram"]})
        disk = status.get("disk", {})
        if disk.get("warning", False):
            alerts.append({"level": "warning", "component": "disk", "message": f"Disco alto: {disk.get('percent')}%", "threshold": self._thresholds["disk"]})
        for alert in alerts:
            self._alerts.append(alert)
            await self.event_bus.publish_async("HEALTH_ALERT", alert, source="health_manager")
            self.logger.warning(f"Alerta de saúde: {alert['message']}")
    
    def register_module(self, name: str, instance: Any) -> None:
        self._modules[name] = {"instance": instance, "registered_at": datetime.now()}
        self.logger.debug(f"Módulo registrado para health check: {name}")
    
    def register_external_service(self, name: str, config: Dict[str, Any]) -> None:
        self._external_services[name] = config
        self.logger.debug(f"Serviço externo registrado: {name}")
    
    def get_status(self) -> Dict[str, Any]:
        return self._last_status
    
    def get_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._alerts[-limit:]
    
    def _add_history(self, status: Dict[str, Any]) -> None:
        self._history.append(status)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
    
    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._history[-limit:]
    
    def set_threshold(self, metric: str, value: float) -> None:
        if metric in self._thresholds:
            self._thresholds[metric] = value
            self.logger.info(f"Threshold {metric}: {value}")
    
    def get_thresholds(self) -> Dict[str, float]:
        return self._thresholds.copy()
    
    async def shutdown(self) -> None:
        self._is_running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        self.logger.info("HealthManager desligado")