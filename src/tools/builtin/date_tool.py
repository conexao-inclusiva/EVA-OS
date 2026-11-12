"""Ferramenta de operações com data/hora."""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import time

from src.tools.base_tool import BaseTool


class DateTool(BaseTool):
    """
    Operações com data e hora.
    """
    
    __plugin_name__ = "date_tool"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Operações com data e hora"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["tool", "date", "time"]
    __plugin_capabilities__ = ["date", "time"]
    __plugin_permissions__ = ["read"]
    __plugin_requires__ = ["logger", "config"]
    
    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "Operações com data e hora",
            "capabilities": ["date", "time"]
        }
    
    def get_required_params(self) -> List[str]:
        return ["action"]
    
    def validate(self, params: Dict[str, Any]) -> bool:
        if "action" not in params:
            return False
        return params["action"] in ["now", "format", "add", "diff", "parse"]
    
    async def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executa operação de data/hora.
        """
        action = params["action"]
        
        result = {
            "type": "date",
            "action": action,
            "success": True
        }
        
        try:
            if action == "now":
                result["data"] = self._get_now()
            elif action == "format":
                result["data"] = self._format_date(params)
            elif action == "add":
                result["data"] = self._add_time(params)
            elif action == "diff":
                result["data"] = self._get_diff(params)
            elif action == "parse":
                result["data"] = self._parse_date(params)
                
        except Exception as e:
            result["error"] = str(e)
            result["success"] = False
        
        return result
    
    def _get_now(self) -> Dict[str, Any]:
        """Obtém data/hora atual."""
        now = datetime.now()
        return {
            "timestamp": now.isoformat(),
            "iso": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": now.weekday(),
            "weekday_name": ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][now.weekday()],
            "unix": int(time.time())
        }
    
    def _format_date(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Formata uma data."""
        date_str = params.get("date")
        format_str = params.get("format", "%Y-%m-%d %H:%M:%S")
        
        if date_str:
            dt = datetime.fromisoformat(date_str)
        else:
            dt = datetime.now()
        
        return {
            "formatted": dt.strftime(format_str),
            "original": dt.isoformat()
        }
    
    def _add_time(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Adiciona tempo a uma data."""
        date_str = params.get("date")
        days = params.get("days", 0)
        hours = params.get("hours", 0)
        minutes = params.get("minutes", 0)
        
        if date_str:
            dt = datetime.fromisoformat(date_str)
        else:
            dt = datetime.now()
        
        result = dt + timedelta(days=days, hours=hours, minutes=minutes)
        
        return {
            "result": result.isoformat(),
            "original": dt.isoformat(),
            "added": {
                "days": days,
                "hours": hours,
                "minutes": minutes
            }
        }
    
    def _get_diff(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calcula diferença entre datas."""
        date1 = datetime.fromisoformat(params.get("date1", datetime.now().isoformat()))
        date2 = datetime.fromisoformat(params.get("date2", datetime.now().isoformat()))
        
        diff = date2 - date1
        
        return {
            "seconds": diff.total_seconds(),
            "minutes": diff.total_seconds() / 60,
            "hours": diff.total_seconds() / 3600,
            "days": diff.total_seconds() / 86400
        }
    
    def _parse_date(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Parseia uma string de data."""
        date_str = params.get("date")
        if not date_str:
            return {"error": "Data não fornecida"}
        
        # Tenta vários formatos
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y"
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return {
                    "parsed": dt.isoformat(),
                    "format": fmt
                }
            except ValueError:
                continue
        
        return {"error": f"Não foi possível parsear: {date_str}"}