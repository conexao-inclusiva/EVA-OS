"""Gerenciamento de fontes de conhecimento."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json


class KnowledgeSource:
    """
    Gerencia fontes de conhecimento.
    
    Cada conhecimento deve ter sua fonte.
    Isso permite rastrear a origem e a confiabilidade.
    """
    
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._sources: Dict[str, Dict[str, Any]] = {}
        self._load()
    
    def _load(self) -> None:
        """Carrega fontes do disco."""
        source_file = self.storage_path / "sources.json"
        if source_file.exists():
            try:
                with open(source_file, "r", encoding="utf-8") as f:
                    self._sources = json.load(f)
            except Exception:
                pass
    
    def _save(self) -> None:
        """Salva fontes no disco."""
        source_file = self.storage_path / "sources.json"
        try:
            with open(source_file, "w", encoding="utf-8") as f:
                json.dump(self._sources, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar fontes: {e}")
    
    def add_source(self, concept: str, source: str, 
                   source_type: str = "manual",
                   metadata: Dict[str, Any] = None) -> str:
        """Adiciona uma fonte para um conceito."""
        source_key = f"{concept}_{source}_{datetime.now().isoformat()}"
        
        self._sources[source_key] = {
            "concept": concept,
            "source": source,
            "source_type": source_type,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
            "confidence": self._calculate_confidence(source, source_type)
        }
        self._save()
        return source_key
    
    def get_sources(self, concept: str) -> List[Dict[str, Any]]:
        """Obtém todas as fontes de um conceito."""
        return [
            data for data in self._sources.values()
            if data["concept"] == concept
        ]
    
    def get_trusted_sources(self, min_confidence: float = 0.7) -> List[Dict[str, Any]]:
        """Obtém fontes com alta confiança."""
        return [
            data for data in self._sources.values()
            if data.get("confidence", 0) >= min_confidence
        ]
    
    def _calculate_confidence(self, source: str, source_type: str) -> float:
        """Calcula confiança de uma fonte."""
        confidence_map = {
            "wikipedia": 0.8,
            "wikidata": 0.85,
            "system": 0.9,
            "expert": 0.9,
            "book": 0.85,
            "article": 0.7,
            "course": 0.75,
            "manual": 0.6,
            "imported": 0.5,
            "learned": 0.4
        }
        
        # Ajusta pelo tipo de fonte
        base = confidence_map.get(source_type, 0.5)
        
        # Ajusta pela fonte específica
        if "wikipedia.org" in source:
            base += 0.1
        elif "gov.br" in source:
            base += 0.1
        elif ".edu" in source:
            base += 0.05
        
        return min(1.0, max(0.0, base))
    
    def update_confidence(self, concept: str, source: str, 
                          new_confidence: float) -> bool:
        """Atualiza confiança de uma fonte."""
        for key, data in self._sources.items():
            if data["concept"] == concept and data["source"] == source:
                data["confidence"] = max(0.0, min(1.0, new_confidence))
                self._save()
                return True
        return False