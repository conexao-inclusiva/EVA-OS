"""Ferramenta de operações de rede."""

from typing import Dict, Any, Optional, List
import socket
import asyncio
import subprocess
import platform

from src.tools.base_tool import BaseTool


class NetworkTool(BaseTool):
    """
    Operações de rede (ping, DNS, etc).
    """
    
    __plugin_name__ = "network_tool"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Operações de rede"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["tool", "network", "ping"]
    __plugin_capabilities__ = ["network", "ping", "dns"]
    __plugin_permissions__ = ["read", "network"]
    __plugin_requires__ = ["logger", "config"]
    
    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "Operações de rede",
            "capabilities": ["network", "ping", "dns"]
        }
    
    def get_required_params(self) -> List[str]:
        return ["action", "host"]
    
    def validate(self, params: Dict[str, Any]) -> bool:
        if "action" not in params or "host" not in params:
            return False
        return params["action"] in ["ping", "dns", "port"]
    
    async def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executa operação de rede.
        """
        action = params["action"]
        host = params["host"]
        timeout = params.get("timeout", 5)
        
        result = {
            "type": "network",
            "action": action,
            "host": host,
            "success": False
        }
        
        try:
            if action == "ping":
                result["data"] = await self._ping(host, timeout)
                result["success"] = True
            elif action == "dns":
                result["data"] = await self._dns(host)
                result["success"] = True
            elif action == "port":
                port = params.get("port", 80)
                result["data"] = await self._port_scan(host, port, timeout)
                result["success"] = True
                
        except Exception as e:
            result["error"] = str(e)
            result["success"] = False
        
        return result
    
    async def _ping(self, host: str, timeout: float) -> Dict[str, Any]:
        """Ping em um host."""
        try:
            ip = socket.gethostbyname(host)
            
            param = "-n" if platform.system().lower() == "windows" else "-c"
            cmd = ["ping", param, "1", "-w", str(int(timeout * 1000)), host]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await proc.wait()
            
            return {
                "host": host,
                "ip": ip,
                "reachable": proc.returncode == 0
            }
        except Exception as e:
            return {
                "host": host,
                "reachable": False,
                "error": str(e)
            }
    
    async def _dns(self, host: str) -> Dict[str, Any]:
        """Resolve DNS."""
        try:
            ip = socket.gethostbyname(host)
            return {
                "host": host,
                "ip": ip,
                "resolved": True
            }
        except Exception as e:
            return {
                "host": host,
                "resolved": False,
                "error": str(e)
            }
    
    async def _port_scan(self, host: str, port: int, timeout: float) -> Dict[str, Any]:
        """Escaneia uma porta."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            
            return {
                "host": host,
                "port": port,
                "open": True
            }
        except Exception:
            return {
                "host": host,
                "port": port,
                "open": False
            }