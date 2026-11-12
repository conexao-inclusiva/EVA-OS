"""Agente de Conhecimento."""

from typing import Dict, Any, Optional

from src.agents.base_agent import BaseAgent
from src.kernel.events import EventBus


class KnowledgeAgent(BaseAgent):
    """
    Agente de Conhecimento.
    
    Responsável por:
    - Responder perguntas factuais
    - Buscar conhecimento
    - Relacionar conceitos
    - Validar informações
    """
    
    __plugin_name__ = "knowledge_agent"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Agente especializado em conhecimento e informação"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["agent", "knowledge", "information"]
    __plugin_capabilities__ = ["knowledge", "facts", "information"]
    __plugin_requires__ = ["event_bus", "logger", "config", "knowledge_manager"]
    
    def __init__(self, event_bus: EventBus, logger, config):
        super().__init__(event_bus, logger, config, name="knowledge")
        self.knowledge_manager = None
    
    async def initialize(self) -> None:
        """Inicializa o agente."""
        # Obtém o knowledge manager do service registry
        registry = getattr(self, "service_registry", None)
        self.knowledge_manager = registry.get("knowledge_manager") if registry is not None else None
        
        await super().initialize()
        self.logger.info("KnowledgeAgent: Pronto para responder perguntas")
    
    async def process(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa uma tarefa de conhecimento.
        """
        if self.knowledge_manager is None:
            registry = getattr(self, "service_registry", None)
            if registry is not None:
                self.knowledge_manager = registry.get("knowledge_manager")
        task_type = task.get("type", "query")
        
        if task_type == "query":
            return await self._handle_query(task)
        elif task_type == "define":
            return await self._handle_definition(task)
        elif task_type == "relate":
            return await self._handle_relation(task)
        elif task_type == "search":
            return await self._handle_search(task)
        else:
            return {"error": f"Tipo de tarefa desconhecido: {task_type}"}
    
    async def _handle_query(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula consulta de conhecimento."""
        query = task.get("query", "")
        user = task.get("user", "unknown")
        
        if not self.knowledge_manager:
            return {"error": "Knowledge Manager não disponível"}
        
        # Busca conhecimento
        results = await self.knowledge_manager.query.execute(query)
        
        return {
            "type": "query",
            "query": query,
            "results": results,
            "user": user,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
    
    async def _handle_definition(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula pedido de definição."""
        concept = task.get("concept", "")
        
        if not self.knowledge_manager:
            return {"error": "Knowledge Manager não disponível"}
        
        node = self.knowledge_manager.get_concept(concept)
        
        if node:
            return {
                "type": "definition",
                "concept": concept,
                "definition": node.get("description"),
                "category": node.get("category"),
                "confidence": node.get("confidence"),
                "found": True
            }
        else:
            return {
                "type": "definition",
                "concept": concept,
                "found": False,
                "message": f"Não encontrei definição para '{concept}'"
            }
    
    async def _handle_relation(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula pedido de relação entre conceitos."""
        source = task.get("source", "")
        target = task.get("target", "")
        
        if not self.knowledge_manager:
            return {"error": "Knowledge Manager não disponível"}
        
        related = self.knowledge_manager.get_related(source)
        
        found = None
        for item in related:
            if item.get("concept") == target:
                found = item
                break
        
        if found:
            return {
                "type": "relation",
                "source": source,
                "target": target,
                "relation_type": found.get("relation_type"),
                "confidence": found.get("confidence"),
                "found": True
            }
        else:
            return {
                "type": "relation",
                "source": source,
                "target": target,
                "found": False,
                "message": f"Não encontrei relação entre '{source}' e '{target}'"
            }
    
    async def _handle_search(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula busca de conhecimento."""
        query = task.get("query", "")
        
        if not self.knowledge_manager:
            return {"error": "Knowledge Manager não disponível"}
        
        results = self.knowledge_manager.index.search(query, limit=10)
        
        return {
            "type": "search",
            "query": query,
            "results": results,
            "count": len(results),
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
    async def start(self) -> None:
        if self._running:
            return
        if not self._initialized:
            raise RuntimeError("Agente nao inicializado")
        await super().start()

    async def shutdown(self) -> None:
        await super().shutdown()

    async def health_check(self) -> dict:
        return await super().health_check()
