"""Ferramenta para pesquisa na biblioteca do Jellyfin."""

import asyncio
from typing import Dict, Any, List
import aiohttp
from src.tools.base_tool import BaseTool


class JellyfinTool(BaseTool):
    """
    Ferramenta para pesquisar filmes na biblioteca Jellyfin e controlar playback.
    """
    
    __plugin_name__ = "jellyfin_tool"
    __plugin_version__ = "1.1.1"
    __plugin_description__ = "Pesquisa e reprodução na biblioteca do Jellyfin com suporte a bypass de LLM"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["tool", "media", "jellyfin"]
    __plugin_capabilities__ = ["media_search", "play"]
    __plugin_permissions__ = ["read", "execute"]
    __plugin_requires__ = ["logger", "config"]
    
    def __init__(self, logger, config):
        super().__init__(logger, config)
        self.api_url = self.config.get("jellyfin.url", "http://localhost:8096")
        self.api_key = self.config.get("jellyfin.api_key", "")
    
    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "Pesquisa filmes na biblioteca Jellyfin e controla playback",
            "capabilities": ["media_search", "play"]
        }
    
    def get_required_params(self) -> List[str]:
        return ["action"]
    
    def validate(self, params: Dict[str, Any]) -> bool:
        if not self.api_key:
            self.logger.error("Jellyfin API key não configurada")
            return False
            
        action = params.get("action")
        if action == "media_search":
            return "query" in params and isinstance(params["query"], str)
        elif action == "play":
            return "item_id" in params and isinstance(params["item_id"], str)
            
        return False
    
    async def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executa uma ação no Jellyfin e anexa metadados de resolução.
        """
        action = params.get("action")
        
        if action == "media_search":
            search_result = await self._search(params["query"])
            if search_result.get("success"):
                # Anexar metadados para bypass do LLM
                search_result["high_confidence"] = True
                search_result["resolved"] = True
            return search_result
            
        elif action == "play":
            play_result = await self._play(params["item_id"])
            if play_result.get("success"):
                play_result["high_confidence"] = True
                play_result["resolved"] = True
            return play_result
            
        return {"success": False, "error": f"Ação desconhecida: {action}"}

    async def _search(self, query: str) -> Dict[str, Any]:
        headers = {"X-Emby-Token": self.api_key}
        search_url = f"{self.api_url}/Search/Hints"
        params_req = {"searchTerm": query, "includeMediaTypes": "Movie", "limit": 10}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers, params=params_req) as response:
                    if response.status != 200:
                        return {"success": False, "error": f"Erro Jellyfin: {response.status}"}
                    data = await response.json()
                    return {"success": True, "query": query, "results": data, "count": len(data)}
        except Exception as e:
            self.logger.error(f"Erro ao buscar: {e}")
            return {"success": False, "error": str(e)}

    async def _play(self, item_id: str) -> Dict[str, Any]:
        try:
            play_url = f"{self.api_url}/web/index.html#!/details?id={item_id}"
            process = await asyncio.create_subprocess_exec("xdg-open", play_url)
            await process.wait()
            
            self.logger.info(f"Comando de reprodução enviado para: {item_id}")
            return {"success": True, "item_id": item_id, "message": "Comando de reprodução enviado"}
        except Exception as e:
            self.logger.error(f"Erro ao reproduzir {item_id}: {e}")
            return {"success": False, "error": str(e)}
