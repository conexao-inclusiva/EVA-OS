"""Ferramenta de execução de comandos shell."""

from typing import Dict, Any, Optional, List
import asyncio
import subprocess
import shlex

from src.tools.base_tool import BaseTool


class ShellTool(BaseTool):
    """
    Executa comandos shell.
    """
    
    __plugin_name__ = "shell_tool"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Executa comandos shell"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["tool", "shell", "command"]
    __plugin_capabilities__ = ["shell", "command_execution"]
    __plugin_permissions__ = ["execute", "shell"]
    __plugin_requires__ = ["logger", "config"]
    
    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "Executa comandos shell",
            "capabilities": ["shell", "command_execution"]
        }
    
    def get_required_params(self) -> List[str]:
        return ["command"]
    
    def get_optional_params(self) -> Dict[str, Any]:
        return {
            "timeout": 10,
            "shell": True
        }
    
    def validate(self, params: Dict[str, Any]) -> bool:
        if "command" not in params:
            return False
        if not isinstance(params["command"], str):
            return False
        return True
    
    async def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executa um comando shell.
        """
        command = params["command"]
        timeout = params.get("timeout", 10)
        use_shell = params.get("shell", True)
        
        result = {
            "type": "shell",
            "command": command,
            "stdout": "",
            "stderr": "",
            "returncode": None
        }
        
        try:
            # Executa
            proc = await asyncio.create_subprocess_shell(
                command if use_shell else command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
                
                result["stdout"] = stdout.decode('utf-8', errors='replace')
                result["stderr"] = stderr.decode('utf-8', errors='replace')
                result["returncode"] = proc.returncode
                result["success"] = proc.returncode == 0
                
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                result["error"] = f"Timeout após {timeout}s"
                result["success"] = False
            
        except Exception as e:
            result["error"] = str(e)
            result["success"] = False
        
        return result