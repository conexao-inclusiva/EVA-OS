"""Grafo de conhecimento."""

from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class KnowledgeNode:
    """Nó no grafo de conhecimento."""
    id: str = field(default_factory=lambda: str(uuid4()))
    concept: str = ""
    description: str = ""
    category: str = "general"
    confidence: float = 0.5
    source: str = "unknown"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "concept": self.concept,
            "description": self.description,
            "category": self.category,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class KnowledgeRelation:
    """Relação entre nós."""
    source_id: str
    target_id: str
    relation_type: str = "related_to"
    confidence: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class KnowledgeGraph:
    """
    Grafo de conhecimento.
    
    Características:
    - Armazena conceitos e suas relações
    - Suporte a múltiplos tipos de relação
    - Grau de confiança em cada relação
    - Busca por conceitos relacionados
    """
    
    def __init__(self):
        self._nodes: Dict[str, KnowledgeNode] = {}
        self._relations: List[KnowledgeRelation] = []
        self._index_by_concept: Dict[str, str] = {}  # conceito -> id
        self._relations_by_source: Dict[str, List[KnowledgeRelation]] = {}
        self._relations_by_target: Dict[str, List[KnowledgeRelation]] = {}
    
    def add_node(self, concept: str, description: str,
                 category: str = "general",
                 confidence: float = 0.5,
                 source: str = "unknown",
                 metadata: Dict[str, Any] = None) -> str:
        """Adiciona um nó ao grafo."""
        # Verifica duplicata
        existing = self._index_by_concept.get(concept.lower())
        if existing:
            # Atualiza o existente
            node = self._nodes[existing]
            node.description = description
            node.category = category
            node.confidence = max(node.confidence, confidence)
            node.updated_at = datetime.now()
            node.metadata.update(metadata or {})
            return node.id
        
        node = KnowledgeNode(
            concept=concept,
            description=description,
            category=category,
            confidence=confidence,
            source=source,
            metadata=metadata or {}
        )
        self._nodes[node.id] = node
        self._index_by_concept[concept.lower()] = node.id
        return node.id
    
    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """Obtém um nó pelo ID."""
        return self._nodes.get(node_id)
    
    def get_by_concept(self, concept: str) -> Optional[KnowledgeNode]:
        """Obtém um nó pelo conceito."""
        node_id = self._index_by_concept.get(concept.lower())
        return self._nodes.get(node_id) if node_id else None
    
    def add_relation(self, source_id: str, target_id: str,
                     relation_type: str = "related_to",
                     confidence: float = 0.5,
                     metadata: Dict[str, Any] = None) -> bool:
        """Adiciona uma relação entre nós."""
        if source_id not in self._nodes or target_id not in self._nodes:
            return False
        
        if source_id == target_id:
            return False
        
        relation = KnowledgeRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            confidence=confidence,
            metadata=metadata or {}
        )
        self._relations.append(relation)
        
        # Indexa
        if source_id not in self._relations_by_source:
            self._relations_by_source[source_id] = []
        self._relations_by_source[source_id].append(relation)
        
        if target_id not in self._relations_by_target:
            self._relations_by_target[target_id] = []
        self._relations_by_target[target_id].append(relation)
        
        return True
    
    def get_relations(self, node_id: str) -> List[KnowledgeRelation]:
        """Obtém todas as relações de um nó."""
        result = []
        result.extend(self._relations_by_source.get(node_id, []))
        result.extend(self._relations_by_target.get(node_id, []))
        return result
    
    def get_related(self, concept: str, relation_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtém nós relacionados a um conceito."""
        node = self.get_by_concept(concept)
        if not node:
            return []
        
        related_ids = set()
        for relation in self._relations:
            if relation_type and relation.relation_type != relation_type:
                continue
            
            if relation.source_id == node.id:
                related_ids.add(relation.target_id)
            elif relation.target_id == node.id:
                related_ids.add(relation.source_id)
        
        result = []
        for node_id in related_ids:
            n = self._nodes.get(node_id)
            if n:
                result.append({
                    "concept": n.concept,
                    "description": n.description,
                    "category": n.category,
                    "confidence": n.confidence,
                    "relation_type": self._get_relation_type(node.id, node_id) if relation_type else "related_to"
                })
        
        return result
    
    def _get_relation_type(self, source_id: str, target_id: str) -> str:
        """Obtém o tipo de relação entre dois nós."""
        for relation in self._relations:
            if relation.source_id == source_id and relation.target_id == target_id:
                return relation.relation_type
            if relation.source_id == target_id and relation.target_id == source_id:
                return relation.relation_type
        return "related_to"
    
    def search(self, query: str) -> List[KnowledgeNode]:
        """Busca nós por texto."""
        query_lower = query.lower()
        results = []
        
        for node in self._nodes.values():
            if (query_lower in node.concept.lower() or
                query_lower in node.description.lower()):
                results.append(node)
        
        return results
    
    def count(self) -> int:
        """Conta nós."""
        return len(self._nodes)
    
    def relation_count(self) -> int:
        """Conta relações."""
        return len(self._relations)