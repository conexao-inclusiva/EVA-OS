"""Validador de conhecimento."""

from typing import List, Dict, Any, Optional
import re


class KnowledgeValidator:
    """
    Valida conhecimento antes de adicionar ao sistema.
    
    Critérios:
    - Conceito não vazio
    - Descrição não vazia
    - Fonte válida
    - Confiança mínima
    - Não duplicado (verificado no grafo)
    """
    
    def __init__(self):
        self._min_confidence = 0.3
        self._max_description_length = 10000
        self._min_description_length = 10
    
    def validate_concept(self, concept: str, description: str, 
                         source: str) -> bool:
        """Valida um conceito."""
        # Conceito não vazio
        if not concept or not concept.strip():
            return False
        
        # Descrição não vazia
        if not description or not description.strip():
            return False
        
        # Descrição muito curta
        if len(description) < self._min_description_length:
            return False
        
        # Descrição muito longa
        if len(description) > self._max_description_length:
            return False
        
        # Fonte válida
        if not source or source == "unknown":
            # Permite source unknown com confiança baixa
            pass
        
        return True
    
    def validate_description(self, description: str) -> bool:
        """Valida uma descrição."""
        if not description or not description.strip():
            return False
        
        if len(description) < self._min_description_length:
            return False
        
        if len(description) > self._max_description_length:
            return False
        
        return True
    
    def validate_relation(self, source: str, target: str, 
                          relation_type: str) -> bool:
        """Valida uma relação."""
        if not source or not target:
            return False
        
        if source == target:
            return False
        
        if not relation_type or not relation_type.strip():
            return False
        
        valid_types = [
            "related_to", "is_a", "part_of", "depends_on",
            "causes", "prevents", "improves", "reduces",
            "similar_to", "opposite_of", "example_of",
            "definition_of", "used_for", "created_by"
        ]
        
        return relation_type in valid_types
    
    def check_consistency(self, node) -> List[str]:
        """Verifica consistência de um nó."""
        issues = []
        
        # Verifica conceito
        if not node.concept or not node.concept.strip():
            issues.append("Conceito vazio")
        
        # Verifica descrição
        if not node.description or not node.description.strip():
            issues.append("Descrição vazia")
        elif len(node.description) < self._min_description_length:
            issues.append(f"Descrição muito curta ({len(node.description)} caracteres)")
        
        # Verifica confiança
        if node.confidence < self._min_confidence:
            issues.append(f"Confiança muito baixa ({node.confidence})")
        
        # Verifica fonte
        if node.source == "unknown":
            issues.append("Fonte desconhecida")
        
        return issues
    
    def validate_source(self, source: str) -> bool:
        """Valida uma fonte."""
        if not source or not source.strip():
            return False
        
        # Lista de fontes válidas
        valid_sources = [
            "wikipedia", "wikidata", "system", "manual", 
            "imported", "learned", "book", "article",
            "video", "course", "expert"
        ]
        
        return source in valid_sources or source.startswith("https://")