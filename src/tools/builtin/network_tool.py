"""Diagnosticos de rede somente leitura, com tempo limitado."""

import asyncio
from datetime import datetime, timezone
import ipaddress
import math
import platform
import re
import socket
from typing import Any, Dict, List

from src.tools.base_tool import BaseTool


class NetworkTool(BaseTool):
    __plugin_name__ = "network_tool"
    __plugin_version__ = "1.1.0"
    __plugin_description__ = "Diagnosticos de rede somente leitura"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["tool", "network", "ping"]
    __plugin_capabilities__ = ["network", "ping", "dns", "port"]
    __plugin_permissions__ = ["read", "network"]
    __plugin_requires__ = ["logger", "config"]

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.__plugin_description__,
            "capabilities": self.get_capabilities(),
            "read_only": True,
        }

    def get_required_params(self) -> List[str]:
        return ["action", "host"]

    def get_optional_params(self) -> Dict[str, Any]:
        return {"timeout": 5, "port": 80}

    def validate(self, params: Dict[str, Any]) -> bool:
        if not isinstance(params, dict):
            return False
        action = params.get("action")
        if not isinstance(action, str) or action not in ("ping", "dns", "port"):
            return False
        host = params.get("host")
        if not isinstance(host, str) or not host or host != host.strip():
            return False
        # Aceita IP literal ou nome DNS; rejeita URLs, opcoes e credenciais.
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if len(host) > 253:
                return False
            labels = host.rstrip(".").split(".")
            if not all(re.fullmatch(
                r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label
            ) for label in labels):
                return False
        timeout = params.get("timeout", 5)
        if (type(timeout) not in (int, float)
                or not math.isfinite(timeout) or not 0.1 <= timeout <= 30):
            return False
        if action == "port":
            port = params.get("port", 80)
            if type(port) is not int or not 1 <= port <= 65535:
                return False
        return True

    async def execute_with_validation(self, params, context=None):
        # Override local: BaseTool atualmente sobrescreve success=False.
        result = await self.execute(params, context)
        self._execution_count += 1
        self._last_execution = datetime.now()
        if not result["success"]:
            self._error_count += 1
        result["tool"] = self.name
        return result

    async def execute(self, params, context=None):
        result = {
            "type": "network",
            "success": False,
            "read_only": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if not self.validate(params):
            result.update(error="Parametros invalidos", error_type="validation")
            return result
        action, host = params["action"], params["host"]
        timeout = params.get("timeout", 5)
        result.update(action=action, host=host)
        try:
            if action == "ping":
                operation = self._ping(host, timeout)
            elif action == "dns":
                operation = self._dns(host)
            else:
                operation = self._port_scan(host, params.get("port", 80), timeout)
            result["data"] = await asyncio.wait_for(operation, timeout=timeout)
            result["success"] = True
        except asyncio.TimeoutError:
            result.update(error="Tempo limite excedido", error_type="timeout")
        except socket.gaierror:
            result.update(error="Falha na resolucao DNS", error_type="dns")
        except FileNotFoundError:
            result.update(error="Executavel ping indisponivel", error_type="unavailable")
        except Exception as exc:
            # Nao retorna mensagens arbitrarias que possam conter dados sensiveis.
            result.update(error="Falha no diagnostico", error_type=type(exc).__name__)
        self.logger.info(
            "NetworkTool action=%s success=%s error_type=%s",
            action, result["success"], result.get("error_type", "none"),
        )
        return result

    async def _resolve(self, host):
        records = await asyncio.get_running_loop().getaddrinfo(
            host, None, type=socket.SOCK_STREAM
        )
        addresses = list(dict.fromkeys(record[4][0] for record in records))
        if not addresses:
            raise socket.gaierror("No addresses")
        return addresses

    async def _dns(self, host):
        addresses = await self._resolve(host)
        return {
            "host": host, "ip": addresses[0], "addresses": addresses,
            "resolved": True,
        }

    async def _ping(self, host, timeout):
        addresses = await self._resolve(host)
        ip = addresses[0]
        system = platform.system().lower()
        if system == "windows":
            command = ["ping", "-n", "1", "-w", str(math.ceil(timeout * 1000)), ip]
        elif system == "linux":
            command = ["ping", "-c", "1", "-W", str(math.ceil(timeout)), ip]
        else:
            raise RuntimeError("Unsupported ping platform")
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await proc.wait()
        finally:
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                await proc.wait()
        if proc.returncode not in (0, 1):
            raise RuntimeError("Ping execution failed")
        return {
            "host": host, "ip": ip, "reachable": proc.returncode == 0,
            "returncode": proc.returncode,
        }

    async def _port_scan(self, host, port, timeout):
        # Uma conexao TCP, sem enviar comandos ou dados ao servico.
        try:
            _, writer = await asyncio.open_connection(host, port)
        except ConnectionRefusedError:
            return {"host": host, "port": port, "open": False, "status": "refused"}
        try:
            return {"host": host, "port": port, "open": True, "status": "open"}
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            finally:
                writer.transport.abort()
