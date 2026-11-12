"""Memória semântica: conceitos persistidos em JSON de forma atômica."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import uuid4
import copy
import json
import os
import tempfile


def _key(value: str) -> str:
    return " ".join(value.casefold().split())


def _confidence(value: float) -> float:
    number = float(value)
    if not 0 <= number <= 1:
        raise ValueError("confidence deve estar entre 0 e 1")
    return number


@dataclass
class SemanticNode:
    id: str = field(default_factory=lambda: str(uuid4()))
    concept: str = ""
    description: str = ""
    category: str = "general"
    confidence: float = 0.5
    source: str = "unknown"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    related_concepts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        result["updated_at"] = self.updated_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: Dict) -> "SemanticNode":
        if not isinstance(data, dict):
            raise ValueError("Nó semântico deve ser um dicionário")
        values = dict(data)
        for key in ("created_at", "updated_at"):
            raw = values.get(key)
            if isinstance(raw, str):
                values[key] = datetime.fromisoformat(raw)
            elif raw is not None and not isinstance(raw, datetime):
                raise ValueError(f"Data inválida: {key}")
        allowed = set(cls.__dataclass_fields__)
        values = {k: v for k, v in values.items() if k in allowed}
        node = cls(**values)
        node.confidence = _confidence(node.confidence)
        if not isinstance(node.metadata, dict) or not isinstance(node.related_concepts, list):
            raise ValueError("Metadados ou relações inválidos")
        return node


class SemanticMemory:
    """Armazena e recupera conceitos; mantém a API existente."""

    def __init__(self, storage_path: Path):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._nodes: Dict[str, SemanticNode] = {}
        self._index_by_concept: Dict[str, str] = {}
        self._file_path = self.storage_path / "semantic_memory.json"
        self._load()

    def _load(self) -> None:
        if not self._file_path.exists():
            return
        try:
            with self._file_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            nodes = payload.get("nodes") if isinstance(payload, dict) else None
            if not isinstance(nodes, dict):
                raise ValueError("Formato de memória semântica inválido")
            loaded = {}
            index = {}
            for node_id, item in nodes.items():
                node = SemanticNode.from_dict(item)
                if not isinstance(node.concept, str) or not node.concept.strip():
                    raise ValueError(f"Conceito inválido no nó {node_id}")
                node.id = str(node_id)
                normalized = _key(node.concept)
                if normalized in index:
                    raise ValueError(f"Conceito duplicado: {node.concept}")
                loaded[node.id] = node
                index[normalized] = node.id
            self._nodes, self._index_by_concept = loaded, index
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            # Não substitui nem apaga o arquivo danificado.
            raise RuntimeError(f"Falha ao carregar {self._file_path}: {exc}") from exc

    def _save(self) -> None:
        payload = {"nodes": {node_id: node.to_dict() for node_id, node in self._nodes.items()}}
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.storage_path,
                prefix=".semantic_memory_", suffix=".tmp", delete=False
            ) as handle:
                temporary = Path(handle.name)
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._file_path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def add(self, concept: str, description: str, category: str = "general",
            confidence: float = 0.5, source: str = "unknown",
            metadata: Dict[str, Any] = None,
            related_concepts: List[str] = None) -> str:
        if not isinstance(concept, str) or not concept.strip():
            raise ValueError("concept deve ser um texto não vazio")
        if not isinstance(description, str):
            raise TypeError("description deve ser texto")
        if metadata is not None and not isinstance(metadata, dict):
            raise TypeError("metadata deve ser dicionário")
        if related_concepts is not None and not isinstance(related_concepts, list):
            raise TypeError("related_concepts deve ser lista")
        confidence = _confidence(confidence)
        concept = concept.strip()
        relations = []
        for item in related_concepts or []:
            if isinstance(item, str) and item.strip() and _key(item) != _key(concept):
                if _key(item) not in {_key(x) for x in relations}:
                    relations.append(item.strip())
        existing_id = self._index_by_concept.get(_key(concept))
        existing = self._nodes.get(existing_id) if existing_id else None
        if existing:
            previous = copy.deepcopy(existing)
            existing.description = description
            existing.confidence = confidence  # atualização explícita, inclusive reduções
            existing.category = category
            existing.source = source
            existing.updated_at = datetime.now()
            existing.metadata.update(copy.deepcopy(metadata or {}))
            known = {_key(x) for x in existing.related_concepts}
            for item in relations:
                if _key(item) not in known:
                    existing.related_concepts.append(item)
                    known.add(_key(item))
            try:
                self._save()
            except Exception:
                self._nodes[existing.id] = previous
                raise
            return existing.id
        node = SemanticNode(concept=concept, description=description, category=category,
                            confidence=confidence, source=source,
                            metadata=copy.deepcopy(metadata or {}), related_concepts=relations)
        self._nodes[node.id] = node
        self._index_by_concept[_key(concept)] = node.id
        try:
            self._save()
        except Exception:
            self._nodes.pop(node.id, None)
            self._index_by_concept.pop(_key(concept), None)
            raise
        return node.id

    def get(self, node_id: str) -> Optional[SemanticNode]:
        node = self._nodes.get(node_id)
        return copy.deepcopy(node) if node else None

    def get_by_concept(self, concept: str) -> Optional[SemanticNode]:
        if not isinstance(concept, str):
            return None
        return self.get(self._index_by_concept.get(_key(concept), ""))

    def search(self, query: str, limit: int = 10) -> List[SemanticNode]:
        if not isinstance(query, str) or not query.strip() or limit <= 0:
            return []
        term = _key(query)
        matches = [node for node in self._nodes.values()
                   if term in _key(node.concept) or term in _key(node.description)]
        matches.sort(key=lambda node: node.confidence, reverse=True)
        return copy.deepcopy(matches[:limit])

    def get_by_category(self, category: str) -> List[SemanticNode]:
        return copy.deepcopy([node for node in self._nodes.values() if node.category == category])

    def get_high_confidence(self, min_confidence: float = 0.7) -> List[SemanticNode]:
        minimum = _confidence(min_confidence)
        return copy.deepcopy([node for node in self._nodes.values() if node.confidence >= minimum])

    def add_relation(self, concept1: str, concept2: str) -> bool:
        if not isinstance(concept1, str) or not isinstance(concept2, str) or _key(concept1) == _key(concept2):
            return False
        id1 = self._index_by_concept.get(_key(concept1))
        id2 = self._index_by_concept.get(_key(concept2))
        if not id1 or not id2:
            return False
        node1, node2 = self._nodes[id1], self._nodes[id2]
        old1, old2 = copy.deepcopy(node1), copy.deepcopy(node2)
        if _key(node2.concept) not in {_key(x) for x in node1.related_concepts}:
            node1.related_concepts.append(node2.concept)
        if _key(node1.concept) not in {_key(x) for x in node2.related_concepts}:
            node2.related_concepts.append(node1.concept)
        node1.updated_at = node2.updated_at = datetime.now()
        try:
            self._save()
        except Exception:
            self._nodes[id1], self._nodes[id2] = old1, old2
            raise
        return True

    def update_confidence(self, concept: str, new_confidence: float) -> bool:
        node_id = self._index_by_concept.get(_key(concept)) if isinstance(concept, str) else None
        if not node_id:
            return False
        confidence = _confidence(new_confidence)
        previous = copy.deepcopy(self._nodes[node_id])
        self._nodes[node_id].confidence = confidence
        self._nodes[node_id].updated_at = datetime.now()
        try:
            self._save()
        except Exception:
            self._nodes[node_id] = previous
            raise
        return True

    def get_recent(self, n: int = 10) -> List[SemanticNode]:
        return copy.deepcopy(sorted(self._nodes.values(), key=lambda x: x.created_at, reverse=True)[:max(n, 0)])

    def get_all(self) -> Dict[str, SemanticNode]:
        return copy.deepcopy(self._nodes)

    def clear(self) -> None:
        previous_nodes, previous_index = self._nodes, self._index_by_concept
        self._nodes, self._index_by_concept = {}, {}
        try:
            self._save()
        except Exception:
            self._nodes, self._index_by_concept = previous_nodes, previous_index
            raise
