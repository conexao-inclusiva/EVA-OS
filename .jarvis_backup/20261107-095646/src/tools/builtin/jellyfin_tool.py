"""Ferramenta para pesquisa na biblioteca do Jellyfin."""

from typing import Dict, Any, List
import aiohttp
from src.tools.base_tool import BaseTool


class JellyfinTool(BaseTool):
    """
    Ferramenta para pesquisar filmes na biblioteca Jellyfin.
    """
    
    __plugin_name__ = "jellyfin_tool"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Pesquisa na biblioteca do Jellyfin"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["tool", "media", "jellyfin"]
    __plugin_capabilities__ = ["media_search"]
    __plugin_permissions__ = ["read"]
    __plugin_requires__ = ["logger", "config"]
    
    def __init__(self, logger, config):
        super().__init__(logger, config)
        self.api_url = self.config.get("jellyfin.url", "http://localhost:8096")
        self.api_key = self.config.get("jellyfin.api_key", "")
    
    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "Pesquisa filmes na biblioteca Jellyfin",
            "capabilities": ["media_search"]
        }
    
    def get_required_params(self) -> List[str]:
        return ["query"]
    
    def validate(self, params: Dict[str, Any]) -> bool:
        if not self.api_key:
            self.logger.error("Jellyfin API key não configurada")
            return False
        return "query" in params and isinstance(params["query"], str)
    
    async def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executa uma busca no Jellyfin.
        """
        query = params["query"]
        headers = {"X-Emby-Token": self.api_key}
        search_url = f"{self.api_url}/Search/Hints"
        
        params_req = {
            "searchTerm": query,
            "includeMediaTypes": "Movie",
            "limit": 10
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers, params=params_req) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "error": f"Erro na API Jellyfin: {response.status}",
                            "query": query
                        }
                    
                    data = await response.json()
                    
                    return {
                        "success": True,
                        "query": query,
                        "results": data,
                        "count": len(data)
                    }
                    
        except Exception as e:
            self.logger.error(f"Erro ao conectar com Jellyfin: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
