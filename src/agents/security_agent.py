"""Agente de Segurança."""

import asyncio
import ipaddress
import math
import re
from copy import deepcopy
from uuid import uuid4
from src.tools.builtin.network_tool import NetworkTool

from typing import Dict, Any, Optional
from datetime import datetime, timezone

from src.agents.base_agent import BaseAgent
from src.kernel.events import EventBus


class SecurityAgent(BaseAgent):
    """
    Agente de Segurança.
    
    Responsável por:
    - Monitorar ameaças
    - Responder a emergências
    - Gerenciar permissões
    - Auditoria
    """
    
    __plugin_name__ = "security_agent"
    __plugin_version__ = "1.1.0"
    __plugin_description__ = "Agente especializado em segurança"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["agent", "security", "emergency"]
    __plugin_capabilities__ = ["security", "emergency", "monitoring"]
    __plugin_requires__ = ["event_bus", "logger", "config"]
    
    def __init__(self, event_bus: EventBus, logger, config):
        super().__init__(event_bus, logger, config, name="security")
        self._alerts = []
        self._incidents = []
    
    async def initialize(self) -> None:
        if self._initialized:
            return
        self._configure_network_monitor()
        await super().initialize()
        self.logger.info("SecurityAgent: inicializado; monitor configurado=" +
                         str(bool(self._network_targets)))


    async def start(self) -> None:
        if not self._initialized:
            raise RuntimeError("SecurityAgent deve ser inicializado antes de start")
        if self._running:
            return
        await super().start()
        if self._network_enabled:
            self._network_task = asyncio.create_task(self._network_loop())
            self.logger.info("SecurityAgent: monitor de conectividade iniciado")


    
    async def process(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa uma tarefa de segurança.
        """
        task_type = task.get("type", "check")
        
        if task_type == "check":
            return await self._handle_check(task)
        elif task_type == "alert":
            return await self._handle_alert(task)
        elif task_type == "emergency":
            return await self._handle_emergency(task)
        elif task_type == "status":
            return await self._handle_status(task)
        else:
            return {"error": f"Tipo de tarefa desconhecido: {task_type}"}
    
    async def _handle_check(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # A tarefa nao pode fornecer destinos nem disparar sondagens arbitrarias.
        snapshot = self._network_snapshot()
        checked = any(item.get("checked_at") for item in snapshot["targets"])
        return {
            "type": "check",
            "success": checked,
            "status": "observation_snapshot" if checked else "not_checked",
            "scope": "connectivity_only",
            "read_only": True,
            "network": snapshot,
            "message": "Consulta das observacoes; nao comprova seguranca, video ou gravacao.",
            "timestamp": datetime.now().isoformat()
        }


    
    async def _handle_alert(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula alerta de segurança."""
        alert = task.get("alert", {})
        self._alerts.append({
            "alert": alert,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "type": "alert",
            "alert": alert,
            "acknowledged": True,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _handle_emergency(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Registra o relato e retorna orientacoes; nao executa protocolos."""
        incident = task.get("incident", {})
        if not isinstance(incident, dict):
            return {
                "type": "emergency",
                "success": False,
                "error": "incident deve ser um dicionario",
                "executed": False,
                "timestamp": datetime.now().isoformat()
            }

        self._incidents.append({
            "incident": dict(incident),
            "timestamp": datetime.now().isoformat()
        })
        incident_type = incident.get("type")
        if incident_type == "fire":
            protocol = "fire_protocol"
            steps = ["Buscar local seguro", "Solicitar ajuda humana de emergencia"]
        elif incident_type == "break_in":
            protocol = "security_protocol"
            steps = ["Buscar local seguro", "Solicitar ajuda humana de seguranca"]
        else:
            protocol = "emergency_protocol"
            steps = ["Solicitar avaliacao humana da situacao"]

        self.logger.warning(
            "SecurityAgent: relato registrado; nenhuma acao externa executada"
        )
        return {
            "type": "emergency",
            "success": True,
            "status": "guidance_only",
            "action": "none",
            "suggested_protocol": protocol,
            "steps": steps,
            "executed": False,
            "external_actions": [],
            "requires_human_review": True,
            "equipment_changes_require_approval": True,
            "message": "Relato registrado em memoria; orientacoes nao executadas.",
            "timestamp": datetime.now().isoformat()
        }

    
    async def _handle_status(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "status",
            "alerts": len(self._alerts),
            "incidents": len(self._incidents),
            "last_alert": deepcopy(self._alerts[-1]) if self._alerts else None,
            "network": self._network_snapshot(),
            "timestamp": datetime.now().isoformat()
        }

    
    async def shutdown(self) -> None:
        task = getattr(self, "_network_task", None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            self._network_task = None
        await super().shutdown()
        self.logger.info("SecurityAgent: desligado")

    
    async def health_check(self) -> Dict[str, Any]:
        health = await super().health_check()
        health["alerts"] = len(self._alerts)
        health["incidents"] = len(self._incidents)
        health["network"] = self._network_snapshot()
        return health

    def _configure_network_monitor(self):
        # Configuracao do servico, nunca parametros recebidos de uma tarefa.
        if isinstance(self.config, dict):
            security = self.config.get("security", {})
            if not isinstance(security, dict):
                raise ValueError("security deve ser um objeto")
            settings = security.get("network_monitor", {})
        else:
            settings = self.config.get("security.network_monitor", {})
        if not isinstance(settings, dict):
            raise ValueError("network_monitor deve ser um objeto")

        enabled = settings.get("enabled", False)
        if type(enabled) is not bool:
            raise ValueError("enabled deve ser booleano")

        def number(key, default, minimum, maximum, integer=False):
            value = settings.get(key, default)
            types = (int,) if integer else (int, float)
            if (type(value) not in types or not math.isfinite(value)
                    or not minimum <= value <= maximum):
                raise ValueError("Valor invalido para " + key)
            return value

        interval = number("interval_seconds", 30, 5, 3600)
        timeout = number("timeout_seconds", 3, 0.1, 30)
        failures = number("failure_threshold", 3, 1, 100, True)
        recoveries = number("recovery_threshold", 2, 1, 100, True)
        targets = settings.get("targets", [])
        if not isinstance(targets, list) or len(targets) > 32:
            raise ValueError("targets deve ser uma lista com ate 32 entradas")

        tool = NetworkTool(self.logger, self.config)
        normalized = []
        identifiers = set()
        endpoints = set()
        for entry in targets:
            if not isinstance(entry, dict):
                raise ValueError("Destino invalido")
            identifier = entry.get("id")
            if (not isinstance(identifier, str)
                    or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identifier)
                    or identifier in identifiers):
                raise ValueError("ID de destino invalido ou duplicado")
            host = entry.get("host")
            if not isinstance(host, str):
                raise ValueError("Host deve ser um IP literal")
            ip = ipaddress.ip_address(host)
            if (ip.version != 4 or ip.is_unspecified or ip.is_multicast
                    or ip.is_reserved or not (ip.is_private or ip.is_loopback)):
                raise ValueError("Destino deve ser um IPv4 local explicito")
            action = entry.get("action")
            params = {"action": action, "host": str(ip), "timeout": timeout}
            if action == "port":
                if "port" not in entry:
                    raise ValueError("Porta obrigatoria")
                params["port"] = entry["port"]
            elif action != "ping":
                raise ValueError("Somente ping e port sao permitidos")
            if not tool.validate(params):
                raise ValueError("Parametros de destino invalidos")
            endpoint = (params["host"], action, params.get("port"))
            if endpoint in endpoints:
                raise ValueError("Sondagem duplicada")
            identifiers.add(identifier)
            endpoints.add(endpoint)
            normalized.append({"id": identifier, "params": params})

        if enabled and not normalized:
            raise ValueError("Monitor habilitado sem destinos")

        self._network_enabled = enabled
        self._network_interval = interval
        self._network_failures = failures
        self._network_recoveries = recoveries
        self._network_targets = tuple(normalized)
        self._network_tool = tool
        self._network_task = None
        self._network_lock = asyncio.Lock()
        self._network_pending = {}
        self._network_status = {
            item["id"]: {
                "id": item["id"],
                "host": item["params"]["host"],
                "action": item["params"]["action"],
                "port": item["params"].get("port"),
                "state": "unknown",
                "last_observation": "not_checked",
                "consecutive_failures": 0,
                "consecutive_successes": 0,
                "checked_at": None,
                "event_status": "none",
            }
            for item in normalized
        }

    def _network_snapshot(self):
        task = getattr(self, "_network_task", None)
        return {
            "enabled": getattr(self, "_network_enabled", False),
            "running": task is not None and not task.done(),
            "scope": "connectivity_only",
            "interval_seconds": getattr(self, "_network_interval", None),
            "targets": deepcopy(list(getattr(self, "_network_status", {}).values())),
        }

    async def _poll_network_once(self):
        async with self._network_lock:
            limit = asyncio.Semaphore(4)

            async def probe(item):
                async with limit:
                    result = await self._network_tool.execute_with_validation(
                        dict(item["params"])
                    )
                    return item, result

            results = await asyncio.gather(
                *(probe(item) for item in self._network_targets)
            )
            for item, result in results:
                state = self._network_status[item["id"]]
                previous = state["state"]
                field = "reachable" if item["params"]["action"] == "ping" else "open"
                positive = (result.get("success") is True
                            and result.get("data", {}).get(field) is True)
                state["checked_at"] = datetime.now(timezone.utc).isoformat()
                state["last_observation"] = (
                    "available" if positive else
                    "negative" if result.get("success") is True else "indeterminate"
                )
                state["error_type"] = result.get("error_type")
                if positive:
                    state["consecutive_failures"] = 0
                    state["consecutive_successes"] = min(
                        state["consecutive_successes"] + 1, self._network_recoveries
                    )
                    if state["consecutive_successes"] >= self._network_recoveries:
                        state["state"] = "available"
                else:
                    state["consecutive_successes"] = 0
                    state["consecutive_failures"] = min(
                        state["consecutive_failures"] + 1, self._network_failures
                    )
                    if state["consecutive_failures"] >= self._network_failures:
                        state["state"] = "unavailable"

                event_name = None
                if state["state"] == "unavailable" and previous != "unavailable":
                    event_name = "security.network.alert"
                elif state["state"] == "available" and previous == "unavailable":
                    event_name = "security.network.recovered"

                if event_name:
                    payload = {
                        "scope": "connectivity_only",
                        "notification_id": str(uuid4()),
                        "timestamp": state["checked_at"],
                        "target": deepcopy(state),
                        "message": (
                            "Conectividade nao confirmada apos falhas consecutivas."
                            if event_name.endswith(".alert")
                            else "Conectividade confirmada apos sucessos consecutivos."
                        ),
                    }
                    self._network_pending[item["id"]] = (event_name, payload)
                    self._alerts.append({
                        "alert": deepcopy(payload),
                        "event": event_name,
                        "timestamp": payload["timestamp"],
                    })
                    self.logger.warning(
                        "SecurityAgent: " + event_name + " target=" + item["id"]
                    )

            # Falhas ao enfileirar sao registradas e tentadas no proximo ciclo.
            for identifier, (event_name, payload) in list(self._network_pending.items()):
                try:
                    await self.event_bus.publish_async(
                        event_name, deepcopy(payload), source=self.name
                    )
                except Exception:
                    self._network_status[identifier]["event_status"] = "publish_failed"
                    self.logger.error("SecurityAgent: falha ao enfileirar evento de rede")
                else:
                    self._network_status[identifier]["event_status"] = "queued"
                    del self._network_pending[identifier]
            return self._network_snapshot()

    async def _network_loop(self):
        while self._running:
            try:
                await self._poll_network_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.error(
                    "SecurityAgent: ciclo de rede falhou: " + type(exc).__name__
                )
            await asyncio.sleep(self._network_interval)

