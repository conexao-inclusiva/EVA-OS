"""Ferramenta de execução de código Python."""

from typing import Dict, Any, Optional, List
import sys
import io
import contextlib
import traceback

from src.tools.base_tool import BaseTool


class PythonTool(BaseTool):
    """
    Executa código Python em um ambiente seguro.
    """
    
    __plugin_name__ = "python_tool"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Executa código Python"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["tool", "python", "code"]
    __plugin_capabilities__ = ["python", "code_execution"]
    __plugin_permissions__ = ["execute", "python"]
    __plugin_requires__ = ["logger", "config"]
    
    def __init__(self, logger, config):
        super().__init__(logger, config)
        self._safe_modules = ['math', 'json', 'datetime', 're', 'random']
    
    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "Executa código Python",
            "capabilities": ["python", "code_execution"],
            "safe_modules": self._safe_modules
        }
    
    def get_required_params(self) -> List[str]:
        return ["code"]
    
    def get_optional_params(self) -> Dict[str, Any]:
        return {
            "timeout": 5,
            "safe_mode": True
        }
    
    def validate(self, params: Dict[str, Any]) -> bool:
        if "code" not in params:
            return False
        if not isinstance(params["code"], str):
            return False
        return True
    
    async def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executa código Python.
        """
        code = params["code"]
        
        stdout = io.StringIO()
        stderr = io.StringIO()
        
        result = {
            "type": "python",
            "code": code,
            "output": "",
            "error": None
        }
        
        try:
            safe_globals = {
                "__builtins__": {
                    name: __builtins__[name] 
                    for name in ['print', 'len', 'str', 'int', 'float', 'list', 
                                 'dict', 'set', 'tuple', 'range', 'sum', 'min', 
                                 'max', 'abs', 'bool', 'type', 'isinstance']
                }
            }
            
            for mod in self._safe_modules:
                try:
                    safe_globals[mod] = __import__(mod)
                except:
                    pass
            
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(code, safe_globals, {})
            
            result["output"] = stdout.getvalue()
            result["error"] = stderr.getvalue() if stderr.getvalue() else None
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
            result["success"] = False
        
        return result