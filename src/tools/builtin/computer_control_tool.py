"""Ferramenta de controle do computador e gerenciamento de aplicativos."""

import os
import sys
import subprocess
import platform
import webbrowser
import asyncio
from typing import Dict, Any, Optional, List
import psutil
from datetime import datetime

from src.tools.base_tool import BaseTool


class ComputerControlTool(BaseTool):
    """
    Ferramenta para controle total do computador, gerenciamento de aplicativos,
    abertura de URLs e execução de comandos do sistema.
    """

    __plugin_name__ = "computer_control_tool"
    __plugin_version__ = "1.1.0"
    __plugin_description__ = "Controle do computador, apps, URLs e comandos do sistema"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["tool", "computer_control", "system", "apps", "browser"]
    __plugin_capabilities__ = ["computer_control", "app_management", "system_config", "web_navigation"]
    __plugin_permissions__ = ["execute", "system", "computer_control"]
    __plugin_requires__ = ["logger", "config"]

    def __init__(self, logger, config):
        super().__init__(logger, config)
        self._system_config_state = {
            "volume": 50,
            "brightness": 100,
            "power_state": "active"
        }

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "Controle do computador, aplicativos e comandos",
            "capabilities": self.get_capabilities()
        }

    def get_required_params(self) -> List[str]:
        return ["action"]

    def get_optional_params(self) -> Dict[str, Any]:
        return {
            "app_name": "",
            "app_path": "",
            "url": "",
            "command": "",
            "pid": None,
            "level": 50,
            "state": "active",
            "env_name": "",
            "env_value": "",
            "args": []
        }

    def validate(self, params: Dict[str, Any]) -> bool:
        if not isinstance(params, dict) or "action" not in params:
            return False
        
        valid_actions = {
            "open_app",
            "open_url",
            "execute_command",
            "list_apps",
            "launch_app", # Alias para open_app
            "close_app",
            "app_status",
            "set_volume",
            "get_volume",
            "set_brightness",
            "get_brightness",
            "power_state",
            "get_env",
            "set_env",
            "list_env"
        }
        return params["action"] in valid_actions

    async def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executa uma ação de controle do computador.
        """
        action = params["action"]
        result = {
            "type": "computer_control",
            "action": action,
            "success": False
        }

        try:
            if action == "open_app" or action == "launch_app":
                app_name = params.get("app_name") or params.get("app_path", "")
                args = params.get("args", [])
                result["data"] = await self._launch_app(app_name, args)
                result["success"] = result["data"].get("launched", False)

            elif action == "open_url":
                url = params.get("url", "")
                result["data"] = await self._open_url(url)
                result["success"] = result["data"].get("opened", False)

            elif action == "execute_command":
                command = params.get("command", "")
                result["data"] = await self._execute_command(command)
                result["success"] = result["data"].get("success", False)

            elif action == "list_apps":
                result["data"] = await self._list_apps()
                result["success"] = True

            elif action == "close_app":
                app_name = params.get("app_name")
                pid = params.get("pid")
                result["data"] = await self._close_app(app_name=app_name, pid=pid)
                result["success"] = result["data"].get("closed", False)

            elif action == "app_status":
                app_name = params.get("app_name")
                pid = params.get("pid")
                result["data"] = await self._app_status(app_name=app_name, pid=pid)
                result["success"] = True

            elif action == "set_volume":
                level = int(params.get("level", 50))
                result["data"] = await self._set_volume(level)
                result["success"] = True

            elif action == "get_volume":
                result["data"] = await self._get_volume()
                result["success"] = True

            elif action == "set_brightness":
                level = int(params.get("level", 100))
                result["data"] = await self._set_brightness(level)
                result["success"] = True

            elif action == "get_brightness":
                result["data"] = await self._get_brightness()
                result["success"] = True

            elif action == "power_state":
                state = params.get("state", "active")
                dry_run = params.get("dry_run", True)
                result["data"] = await self._power_state(state, dry_run=dry_run)
                result["success"] = True

            elif action == "get_env":
                name = params.get("env_name") or params.get("name", "")
                result["data"] = await self._get_env(name)
                result["success"] = True

            elif action == "set_env":
                name = params.get("env_name") or params.get("name", "")
                value = params.get("env_value") if "env_value" in params else params.get("value", "")
                result["data"] = await self._set_env(name, str(value))
                result["success"] = True

            elif action == "list_env":
                result["data"] = await self._list_env()
                result["success"] = True

        except Exception as e:
            self.logger.error(f"[ComputerControlTool] Erro ao executar ação {action}: {e}")
            result["error"] = str(e)
            result["success"] = False

        return result

    async def _open_url(self, url: str) -> Dict[str, Any]:
        """Abre uma URL no navegador padrão."""
        if not url:
            return {"opened": False, "error": "URL não especificada"}
        
        try:
            # Garante que a URL tenha um esquema
            if not url.startswith(("http://", "https://", "file://")):
                if "." not in url and "youtube" in url.lower():
                    url = "https://www.youtube.com"
                else:
                    url = "https://" + url

            self.logger.info(f"[ComputerControlTool] Abrindo URL: {url}")
            # Abre no navegador
            webbrowser.open(url)
            
            return {
                "opened": True,
                "url": url,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"[ComputerControlTool] Falha ao abrir URL {url}: {e}")
            return {
                "opened": False,
                "url": url,
                "error": str(e)
            }

    async def _execute_command(self, command: str) -> Dict[str, Any]:
        """Executa um comando shell de forma assíncrona."""
        if not command:
            return {"success": False, "error": "Comando não especificado"}

        try:
            self.logger.info(f"[ComputerControlTool] Executando comando: {command}")
            
            # Executa usando o shell do sistema
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace'),
                "returncode": proc.returncode
            }
        except Exception as e:
            self.logger.error(f"[ComputerControlTool] Erro ao executar comando: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _list_apps(self) -> Dict[str, Any]:
        """Lista aplicativos em execução."""
        running = []
        for proc in psutil.process_iter(['pid', 'name', 'status']):
            try:
                info = proc.info
                if info['name'] and info['name'] not in [p['name'] for p in running]:
                    running.append({
                        "pid": info['pid'],
                        "name": info['name'],
                        "status": info['status']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return {
            "running_count": len(running),
            "running_apps": running[:50]
        }

    async def _launch_app(self, app_name: str, args: List[str] = None) -> Dict[str, Any]:
        """Inicia um aplicativo pelo nome ou caminho."""
        if not app_name:
            return {"launched": False, "error": "Nome ou caminho do aplicativo não especificado"}

        cmd = [app_name] + (args or [])
        try:
            # Tratamento especial para Windows se não for um caminho absoluto
            use_shell = (platform.system() == "Windows" and not os.path.isabs(app_name))
            
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=use_shell,
                start_new_session=True
            )
            return {
                "launched": True,
                "pid": proc.pid,
                "app_name": app_name
            }
        except Exception as e:
            self.logger.error(f"[ComputerControlTool] Erro ao iniciar {app_name}: {e}")
            return {
                "launched": False,
                "app_name": app_name,
                "error": str(e)
            }

    async def _close_app(self, app_name: Optional[str] = None, pid: Optional[int] = None) -> Dict[str, Any]:
        """Fecha um aplicativo pelo PID ou pelo nome."""
        if not app_name and pid is None:
            return {"closed": False, "error": "É necessário informar o app_name ou pid"}

        closed_pids = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                info = proc.info
                match_pid = (pid is not None and info['pid'] == pid)
                match_name = (app_name is not None and info['name'] and info['name'].lower() == app_name.lower())
                if match_pid or match_name:
                    proc.terminate()
                    closed_pids.append(info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                self.logger.warning(f"[ComputerControlTool] Erro ao tentar encerrar processo {proc.pid}: {e}")

        return {
            "closed": len(closed_pids) > 0,
            "closed_pids": closed_pids,
            "target": app_name or pid
        }

    async def _app_status(self, app_name: Optional[str] = None, pid: Optional[int] = None) -> Dict[str, Any]:
        """Consulta o status de um aplicativo."""
        if not app_name and pid is None:
            return {"running": False, "error": "É necessário informar o app_name ou pid"}

        matches = []
        for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                match_pid = (pid is not None and info['pid'] == pid)
                match_name = (app_name is not None and info['name'] and info['name'].lower() == app_name.lower())
                if match_pid or match_name:
                    matches.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return {
            "running": len(matches) > 0,
            "count": len(matches),
            "instances": matches
        }

    async def _set_volume(self, level: int) -> Dict[str, Any]:
        """Ajusta o volume do sistema (0-100)."""
        clamped = max(0, min(100, level))
        self._system_config_state["volume"] = clamped

        if platform.system() == "Windows":
            try:
                powershell_cmd = (
                    f"$wsh = New-Object -ComObject WScript.Shell; "
                    f"1..50 | ForEach-Object {{ $wsh.SendKeys([char]174) }}; "
                    f"1..{int(clamped / 2)} | ForEach-Object {{ $wsh.SendKeys([char]175) }}"
                )
                subprocess.run(["powershell", "-Command", powershell_cmd], capture_output=True, timeout=5)
            except Exception as e:
                self.logger.warning(f"[ComputerControlTool] Falha ao ajustar volume via PowerShell: {e}")
        elif platform.system() == "Linux":
            try:
                subprocess.run(["amixer", "-D", "pulse", "sset", "Master", f"{clamped}%"], capture_output=True, timeout=5)
            except Exception as e:
                self.logger.warning(f"[ComputerControlTool] Falha ao ajustar volume via amixer: {e}")

        return {"volume": clamped, "status": "set"}

    async def _get_volume(self) -> Dict[str, Any]:
        """Obtém o volume atual do sistema."""
        return {"volume": self._system_config_state.get("volume", 50)}

    async def _set_brightness(self, level: int) -> Dict[str, Any]:
        """Ajusta o brilho da tela (0-100)."""
        clamped = max(0, min(100, level))
        self._system_config_state["brightness"] = clamped

        if platform.system() == "Windows":
            try:
                powershell_cmd = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {clamped})"
                subprocess.run(["powershell", "-Command", powershell_cmd], capture_output=True, timeout=5)
            except Exception as e:
                self.logger.warning(f"[ComputerControlTool] Falha ao ajustar brilho via PowerShell: {e}")

        return {"brightness": clamped, "status": "set"}

    async def _get_brightness(self) -> Dict[str, Any]:
        """Obtém o brilho atual do sistema."""
        return {"brightness": self._system_config_state.get("brightness", 100)}

    async def _power_state(self, state: str, dry_run: bool = True) -> Dict[str, Any]:
        """Gerencia o estado de energia do sistema."""
        valid_states = ["lock", "sleep", "shutdown", "restart", "active"]
        if state not in valid_states:
            return {"success": False, "error": f"Estado inválido. Opções: {valid_states}"}

        self._system_config_state["power_state"] = state
        executed = False

        if not dry_run:
            if state == "lock":
                if platform.system() == "Windows":
                    subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False)
                    executed = True
            elif state == "shutdown":
                if platform.system() == "Windows":
                    subprocess.run(["shutdown", "/s", "/t", "0"], check=False)
                    executed = True
                elif platform.system() == "Linux":
                    subprocess.run(["shutdown", "-h", "now"], check=False)
                    executed = True
            elif state == "restart":
                if platform.system() == "Windows":
                    subprocess.run(["shutdown", "/r", "/t", "0"], check=False)
                    executed = True
                elif platform.system() == "Linux":
                    subprocess.run(["shutdown", "-r", "now"], check=False)
                    executed = True

        return {
            "state": state,
            "dry_run": dry_run,
            "executed": executed
        }

    async def _get_env(self, name: str) -> Dict[str, Any]:
        """Obtém o valor de uma variável de ambiente."""
        if not name:
            return {"error": "Nome da variável não especificado"}
        val = os.environ.get(name)
        return {
            "name": name,
            "value": val,
            "exists": val is not None
        }

    async def _set_env(self, name: str, value: str) -> Dict[str, Any]:
        """Define o valor de uma variável de ambiente."""
        if not name:
            return {"error": "Nome da variável não especificado"}
        os.environ[name] = str(value)
        return {
            "name": name,
            "value": value,
            "status": "set"
        }

    async def _list_env(self) -> Dict[str, Any]:
        """Lista todas as variáveis de ambiente."""
        env_dict = dict(os.environ)
        return {
            "count": len(env_dict),
            "env": env_dict
        }
