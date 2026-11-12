"""Índice de conhecimento para busca rápida."""

from typing import List, Dict, Any, Set
from collections import defaultdict
import re


class KnowledgeIndex:
    """
    Índice para busca rápida em conhecimento.
    
    Características:
    - Indexação por palavras-chave
    - Busca por termos
    - Ranking por relevância
    - Suporte a busca fuzzy (futuro)
    """
    
    def __init__(self):
        self._index: Dict[str, List[str]] = defaultdict(list)  # palavra -> [node_ids]
        self._node_cache: Dict[str, Dict[str, Any]] = {}
        self._term_count: Dict[str, int] = defaultdict(int)  # palavra -> contagem
    
    def index_concept(self, concept: str, description: str, 
                      category: str, node_id: str) -> None:
        """Indexa um conceito."""
        # Palavras do conceito
        words = self._extract_words(concept)
        for word in words:
            if len(word) > 2:
                self._index[word].append(node_id)
                self._term_count[word] += 1
        
        # Palavras da descrição
        desc_words = self._extract_words(description)
        for word in desc_words[:20]:  # Limita
            if len(word) > 3:
                self._index[word].append(node_id)
                self._term_count[word] += 1
        
        # Cache
        self._node_cache[node_id] = {
            "concept": concept,
            "description": description,
            "category": category
        }
    
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Busca por palavras-chave."""
        words = self._extract_words(query)
        
        if not words:
            return []
        
        # Conta ocorrências
        scores: Dict[str, float] = defaultdict(float)
        
        for word in words:
            if len(word) <= 2:
                continue
            
            matches = self._index.get(word, [])
            for node_id in matches:
                # Score base
                scores[node_id] += 1.0
                
                # Bonus por termo específico
                if len(word) > 5:
                    scores[node_id] += 0.5
        
        # Normaliza por term frequency
        for node_id in scores:
            scores[node_id] = scores[node_id] / (1 + len(words))
        
        # Ordena por score
        sorted_results = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Retorna resultados
        results = []
        for node_id, score in sorted_results[:limit]:
            if node_id in self._node_cache:
                results.append({
                    "node_id": node_id,
                    **self._node_cache[node_id],
                    "score": score
                })
        
        return results
    
    def _extract_words(self, text: str) -> List[str]:
        """Extrai palavras de um texto."""
        # Remove pontuação e caracteres especiais
        cleaned = re.sub(r'[^\w\s]', ' ', text.lower())
        # Divide em palavras
        words = cleaned.split()
        # Remove palavras comuns (stopwords)
        stopwords = {'a', 'o', 'e', 'é', 'de', 'da', 'do', 'que', 'com', 'para', 
                     'por', 'um', 'uma', 'em', 'no', 'na', 'os', 'as', 'se', 
                     'mas', 'como', 'quando', 'onde', 'porque', 'entao', 'então',
                     'isso', 'aquilo', 'este', 'esta', 'esses', 'essas'}
        return [w for w in words if w not in stopwords]
    
    def get_terms(self, query: str) -> List[str]:
        """Obtém termos de uma consulta."""
        return self._extract_words(query)
    
    def count(self) -> int:
        """Conta termos indexados."""
        return len(self._index)
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas do índice."""
        return {
            "total_terms": len(self._index),
            "total_nodes": len(self._node_cache),
            "total_occurrences": sum(self._term_count.values()),
            "top_terms": sorted(self._term_count.items(), key=lambda x: x[1], reverse=True)[:10]
        }