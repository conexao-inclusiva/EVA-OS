"""Linguagem de consulta para conhecimento."""

from typing import Dict, Any, List, Optional
import re


class KnowledgeQuery:
    """
    Linguagem de consulta para conhecimento.
    
    Suporta:
    - Busca por conceito: "O que é X?"
    - Busca por relação: "O que X tem a ver com Y?"
    - Busca por categoria: "Conceitos sobre tecnologia"
    - Consulta hierárquica: "O que é parte de X?"
    """
    
    def __init__(self, knowledge_manager):
        self.knowledge_manager = knowledge_manager
        self.logger = knowledge_manager.logger
    
    async def execute(self, query: str) -> Dict[str, Any]:
        """Executa uma consulta."""
        query_lower = query.lower().strip()
        
        # Detecta tipo de consulta
        if self._is_definition_query(query_lower):
            return await self._handle_definition(query_lower)
        elif self._is_relationship_query(query_lower):
            return await self._handle_relationship(query_lower)
        elif self._is_category_query(query_lower):
            return await self._handle_category(query_lower)
        elif self._is_hierarchy_query(query_lower):
            return await self._handle_hierarchy(query_lower)
        else:
            return await self._handle_general(query_lower)
    
    def _is_definition_query(self, query: str) -> bool:
        """Verifica se é uma consulta de definição."""
        patterns = [
            r"^o que (é|e) ",
            r"^quem (é|e) ",
            r"^defina ",
            r"^explique (o que|quem) ",
            r"^o que significa "
        ]
        return any(re.search(p, query) for p in patterns)
    
    def _is_relationship_query(self, query: str) -> bool:
        """Verifica se é uma consulta de relação."""
        patterns = [
            r" relação entre ",
            r" tem a ver com ",
            r" diferente de ",
            r" similar a "
        ]
        return any(p in query for p in patterns)
    
    def _is_category_query(self, query: str) -> bool:
        """Verifica se é uma consulta por categoria."""
        patterns = [
            r"conceitos sobre ",
            r"categor[aá] ",
            r"tipos de "
        ]
        return any(p in query for p in patterns)
    
    def _is_hierarchy_query(self, query: str) -> bool:
        """Verifica se é uma consulta hierárquica."""
        patterns = [
            r"parte de ",
            r"subcategoria",
            r"tipo de ",
            r"hierarquia"
        ]
        return any(p in query for p in patterns)
    
    async def _handle_definition(self, query: str) -> Dict[str, Any]:
        """Processa consulta de definição."""
        # Extrai o conceito
        words = query.split()
        concept = None
        
        for i, word in enumerate(words):
            if word in ["é", "e", "o", "a", "que"]:
                if i + 1 < len(words):
                    concept = words[i + 1]
                    break
        
        if not concept:
            # Tenta pegar a última palavra
            concept = words[-1] if words else None
        
        if concept:
            node = self.knowledge_manager.graph.get_by_concept(concept)
            if node:
                return {
                    "type": "definition",
                    "query": query,
                    "concept": concept,
                    "found": True,
                    "definition": node.description,
                    "category": node.category,
                    "confidence": node.confidence,
                    "source": node.source
                }
        
        return {
            "type": "definition",
            "query": query,
            "found": False,
            "message": f"Não encontrei definição para: {concept or query}"
        }
    
    async def _handle_relationship(self, query: str) -> Dict[str, Any]:
        """Processa consulta de relação."""
        # Busca conceitos na consulta
        concepts = []
        words = query.split()
        
        for word in words:
            if len(word) > 3:
                node = self.knowledge_manager.graph.get_by_concept(word)
                if node:
                    concepts.append(word)
                elif len(concepts) < 2:
                    # Verifica se é uma palavra composta
                    pass
        
        if len(concepts) >= 2:
            source = concepts[0]
            target = concepts[1]
            
            relations = self.knowledge_manager.graph.get_related(source)
            target_info = None
            
            for rel in relations:
                if rel["concept"] == target:
                    target_info = rel
                    break
            
            if target_info:
                return {
                    "type": "relationship",
                    "query": query,
                    "source": source,
                    "target": target,
                    "found": True,
                    "relation_type": target_info.get("relation_type", "related_to"),
                    "confidence": target_info.get("confidence", 0.5)
                }
        
        return {
            "type": "relationship",
            "query": query,
            "found": False,
            "message": "Não encontrei relação entre os conceitos"
        }
    
    async def _handle_category(self, query: str) -> Dict[str, Any]:
        """Processa consulta por categoria."""
        # Extrai categoria
        words = query.split()
        category = None
        
        for i, word in enumerate(words):
            if word in ["sobre", "de", "em"]:
                if i + 1 < len(words):
                    category = words[i + 1]
                    break
        
        if not category:
            category = words[-1] if words else None
        
        if category:
            # Busca conceitos por categoria
            nodes = self.knowledge_manager.graph.get_by_category(category)
            
            if nodes:
                return {
                    "type": "category",
                    "query": query,
                    "category": category,
                    "found": True,
                    "concepts": [n.concept for n in nodes[:10]],
                    "count": len(nodes)
                }
        
        return {
            "type": "category",
            "query": query,
            "found": False,
            "message": f"Não encontrei conceitos na categoria: {category or query}"
        }
    
    async def _handle_hierarchy(self, query: str) -> Dict[str, Any]:
        """Processa consulta hierárquica."""
        # Extrai conceito
        words = query.split()
        concept = None
        
        for word in words:
            if len(word) > 3:
                node = self.knowledge_manager.graph.get_by_concept(word)
                if node:
                    concept = word
                    break
        
        if concept:
            hierarchy = self.knowledge_manager.relationship.get_hierarchy(concept)
            if hierarchy.get("parents") or hierarchy.get("children"):
                return {
                    "type": "hierarchy",
                    "query": query,
                    "concept": concept,
                    "found": True,
                    "parents": hierarchy.get("parents", []),
                    "children": hierarchy.get("children", [])
                }
        
        return {
            "type": "hierarchy",
            "query": query,
            "found": False,
            "message": f"Não encontrei hierarquia para: {concept or query}"
        }
    
    async def _handle_general(self, query: str) -> Dict[str, Any]:
        """Processa consulta geral."""
        # Busca no índice
        results = self.knowledge_manager.index.search(query, limit=5)
        
        if results:
            return {
                "type": "general",
                "query": query,
                "found": True,
                "results": results,
                "count": len(results)
            }
        
        return {
            "type": "general",
            "query": query,
            "found": False,
            "message": "Não encontrei resultados para sua consulta"
        }