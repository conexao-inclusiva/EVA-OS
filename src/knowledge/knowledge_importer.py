"""Importador de conhecimento externo."""

from typing import Dict, Any, List, Optional
import aiohttp
import json


class KnowledgeImporter:
    """
    Importa conhecimento de fontes externas.
    
    Fontes suportadas:
    - Wikipedia
    - Wikidata
    - Arquivos locais
    - APIs externas
    """
    
    def __init__(self, knowledge_manager):
        self.knowledge_manager = knowledge_manager
        self.logger = knowledge_manager.logger
    
    async def import_from(self, source_type: str, query: str) -> Dict[str, Any]:
        """Importa conhecimento de uma fonte."""
        if source_type == "wikipedia":
            return await self._import_wikipedia(query)
        elif source_type == "wikidata":
            return await self._import_wikidata(query)
        elif source_type == "local":
            return await self._import_local(query)
        else:
            return {"error": f"Fonte não suportada: {source_type}"}
    
    async def _import_wikipedia(self, query: str) -> Dict[str, Any]:
        """Importa da Wikipedia."""
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        title = data.get("title", query)
                        extract = data.get("extract", "")
                        
                        if extract:
                            # Adiciona ao conhecimento
                            self.knowledge_manager.graph.add_node(
                                concept=title,
                                description=extract[:2000],
                                category="wikipedia",
                                confidence=0.8,
                                source=f"wikipedia: {query}",
                                metadata={"url": url, "full_extract": extract}
                            )
                            
                            self.knowledge_manager.index.index_concept(
                                title, extract[:2000], "wikipedia",
                                self.knowledge_manager.graph.get_by_concept(title).id
                            )
                            
                            return {
                                "success": True,
                                "concept": title,
                                "source": "wikipedia",
                                "description": extract[:200]
                            }
                    
                    return {"error": f"Erro ao buscar {query}: {response.status}"}
                    
        except Exception as e:
            self.logger.error(f"Erro na importação Wikipedia: {e}")
            return {"error": str(e)}
    
    async def _import_wikidata(self, query: str) -> Dict[str, Any]:
        """Importa da Wikidata."""
        try:
            # Busca entidade
            url = f"https://www.wikidata.org/wiki/Special:EntityData/{query}.json"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Processa entidade
                        entity = data.get("entities", {}).get(query, {})
                        labels = entity.get("labels", {})
                        descriptions = entity.get("descriptions", {})
                        
                        name = labels.get("en", {}).get("value", query)
                        description = descriptions.get("en", {}).get("value", "")
                        
                        if description:
                            self.knowledge_manager.graph.add_node(
                                concept=name,
                                description=description[:1000],
                                category="wikidata",
                                confidence=0.85,
                                source=f"wikidata: {query}",
                                metadata={"entity_id": query}
                            )
                            
                            return {
                                "success": True,
                                "concept": name,
                                "source": "wikidata",
                                "description": description
                            }
                    
                    return {"error": f"Erro ao buscar {query}: {response.status}"}
                    
        except Exception as e:
            self.logger.error(f"Erro na importação Wikidata: {e}")
            return {"error": str(e)}
    
    async def _import_local(self, path: str) -> Dict[str, Any]:
        """Importa de um arquivo local."""
        try:
            # TODO: Implementar importação de arquivos locais
            return {"success": False, "error": "Importação local não implementada"}
        except Exception as e:
            return {"error": str(e)}