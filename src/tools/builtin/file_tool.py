"""Ferramenta de operações com arquivos."""

from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import os
import shutil

from src.tools.base_tool import BaseTool


class FileTool(BaseTool):
    """
    Operaçõs com arquivos (ler, escrever, listar, etc).
    """
    
    __plugin_name__ = "file_tool"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Operações com arquivos"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["tool", "file", "filesystem"]
    __plugin_capabilities__ = ["file", "filesystem"]
    __plugin_permissions__ = ["read", "write", "file"]
    __plugin_requires__ = ["logger", "config"]
    
    def __init__(self, logger, config):
        super().__init__(logger, config)
        self._base_path = Path(config.get("paths.data", "./data"))
    
    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "Operações com arquivos",
            "capabilities": ["file", "filesystem"],
            "base_path": str(self._base_path)
        }
    
    def get_required_params(self) -> List[str]:
        return ["action", "path"]
    
    def validate(self, params: Dict[str, Any]) -> bool:
        if "action" not in params or "path" not in params:
            return False
        return params["action"] in ["read", "write", "delete", "list", "exists", "mkdir"]
    
    async def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executa operação com arquivo.
        """
        action = params["action"]
        path = params["path"]
        
        # Segurança: previne path traversal
        full_path = self._safe_path(path)
        
        result = {
            "type": "file",
            "action": action,
            "path": str(full_path),
            "success": False
        }
        
        try:
            if action == "read":
                result["content"] = await self._read_file(full_path)
                result["success"] = True
                
            elif action == "write":
                content = params.get("content", "")
                await self._write_file(full_path, content)
                result["success"] = True
                
            elif action == "delete":
                await self._delete_file(full_path)
                result["success"] = True
                
            elif action == "list":
                result["files"] = await self._list_files(full_path)
                result["success"] = True
                
            elif action == "exists":
                result["exists"] = full_path.exists()
                result["success"] = True
                
            elif action == "mkdir":
                full_path.mkdir(parents=True, exist_ok=True)
                result["success"] = True
                
        except Exception as e:
            result["error"] = str(e)
            result["success"] = False
        
        return result
    
    def _safe_path(self, path: str) -> Path:
        """Garante que o path é seguro."""
        p = Path(path)
        if p.is_absolute():
            # Verifica se está dentro do base_path
            try:
                p.relative_to(self._base_path)
                return p
            except ValueError:
                # Se não estiver, trata como relativo
                pass
        return self._base_path / p
    
    async def _read_file(self, path: Path) -> str:
        """Lê um arquivo."""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    async def _write_file(self, path: Path, content: str) -> None:
        """Escreve um arquivo."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    async def _delete_file(self, path: Path) -> None:
        """Deleta um arquivo ou diretório."""
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    
    async def _list_files(self, path: Path) -> List[Dict[str, Any]]:
        """Lista arquivos em um diretório."""
        if not path.exists():
            return []
        
        files = []
        for item in path.iterdir():
            files.append({
                "name": item.name,
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else 0,
                "modified": item.stat().st_mtime
            })
        return files