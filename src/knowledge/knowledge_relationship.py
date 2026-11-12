"""Gerenciamento de relacionamentos entre conceitos."""

from typing import Dict, Any, List, Optional


class KnowledgeRelationship:
    """
    Gerencia relacionamentos entre conceitos.
    
    Tipos de relacionamento:
    - is_a: hierarquia
    - part_of: composição
    - depends_on: dependência
    - causes: causalidade
    - related_to: associação
    - opposite_of: oposição
    - similar_to: similaridade
    """
    
    def __init__(self, knowledge_manager):
        self.knowledge_manager = knowledge_manager
        self.logger = knowledge_manager.logger
        
        # Tipos de relacionamento válidos
        self.valid_types = {
            "is_a", "part_of", "depends_on", "causes", "prevents",
            "improves", "reduces", "related_to", "similar_to",
            "opposite_of", "example_of", "definition_of",
            "used_for", "created_by"
        }
    
    def add_relation(self, source: str, target: str, 
                     relation_type: str = "related_to") -> bool:
        """Adiciona uma relação entre conceitos."""
        # Valida
        if relation_type not in self.valid_types:
            self.logger.warning(f"Tipo de relação inválido: {relation_type}")
            return False
        
        source_node = self.knowledge_manager.graph.get_by_concept(source)
        target_node = self.knowledge_manager.graph.get_by_concept(target)
        
        if not source_node or not target_node:
            self.logger.warning(f"Conceito não encontrado: {source} ou {target}")
            return False
        
        # Adiciona relação
        return self.knowledge_manager.graph.add_relation(
            source_id=source_node.id,
            target_id=target_node.id,
            relation_type=relation_type
        )
    
    def get_relations(self, concept: str) -> List[Dict[str, Any]]:
        """Obtém todas as relações de um conceito."""
        node = self.knowledge_manager.graph.get_by_concept(concept)
        if not node:
            return []
        
        relations = self.knowledge_manager.graph.get_relations(node.id)
        
        result = []
        for rel in relations:
            source = self.knowledge_manager.graph.get_node(rel.source_id)
            target = self.knowledge_manager.graph.get_node(rel.target_id)
            
            if source and target:
                direction = "source" if source.concept == concept else "target"
                result.append({
                    "source": source.concept,
                    "target": target.concept,
                    "type": rel.relation_type,
                    "confidence": rel.confidence,
                    "direction": direction
                })
        
        return result
    
    def get_hierarchy(self, concept: str) -> Dict[str, Any]:
        """Obtém a hierarquia de um conceito."""
        node = self.knowledge_manager.graph.get_by_concept(concept)
        if not node:
            return {}
        
        result = {
            "concept": concept,
            "parents": [],
            "children": [],
            "siblings": []
        }
        
        # Busca is_a relations
        for rel in self.knowledge_manager.graph.get_relations(node.id):
            if rel.relation_type == "is_a":
                source = self.knowledge_manager.graph.get_node(rel.source_id)
                target = self.knowledge_manager.graph.get_node(rel.target_id)
                
                if source and target:
                    if source.id == node.id:
                        result["parents"].append(target.concept)
                    else:
                        result["children"].append(source.concept)
        
        return result