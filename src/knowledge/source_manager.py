"""Gerenciador de fontes de conhecimento."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import uuid4


@dataclass
class KnowledgeSource:
    """Fonte de conhecimento."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    type: str = ""  # book, article, video, course, etc.
    author: str = ""
    url: Optional[str] = None
    trust_score: float = 0.5  # 0.0 a 1.0
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SourceManager:
    """
    Gerencia fontes de conhecimento.
    Cada conhecimento deve ter sua fonte.
    """
    
    def __init__(self):
        self._sources: Dict[str, KnowledgeSource] = {}
    
    def add_source(self, source: KnowledgeSource) -> str:
        """Adiciona uma fonte."""
        self._sources[source.id] = source
        return source.id
    
    def get_source(self, source_id: str) -> Optional[KnowledgeSource]:
        """Obtém uma fonte pelo ID."""
        return self._sources.get(source_id)
    
    def get_by_type(self, source_type: str) -> List[KnowledgeSource]:
        """Obtém fontes por tipo."""
        return [s for s in self._sources.values() if s.type == source_type]
    
    def get_trusted_sources(self, min_trust: float = 0.7) -> List[KnowledgeSource]:
        """Obtém fontes com alto grau de confiança."""
        return [s for s in self._sources.values() if s.trust_score >= min_trust]
    
    def update_trust(self, source_id: str, new_score: float) -> None:
        """Atualiza o grau de confiança de uma fonte."""
        if source_id in self._sources:
            self._sources[source_id].trust_score = max(0.0, min(1.0, new_score))