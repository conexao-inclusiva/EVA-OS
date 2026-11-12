# -*- coding: utf-8 -*-
"""EntityTracker - Rastreia entidades mencionadas na conversa."""

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional


class EntityTracker:
    """Mantém entidades, apelidos e frequência de menção durante a sessão."""

    def __init__(self):
        self._entities: Dict[str, Dict[str, Any]] = {}
        self.logger = None

    def set_logger(self, logger):
        """Define o logger."""
        self.logger = logger

    @staticmethod
    def _normalize(value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return " ".join(value.split()).casefold()

    def _find_key(self, name: str) -> Optional[str]:
        key = self._normalize(name)
        if not key:
            return None
        if key in self._entities:
            return key
        for stored_key, entity in self._entities.items():
            if any(self._normalize(alias) == key for alias in entity.get("aliases", [])):
                return stored_key
        return None

    @classmethod
    def _clean_aliases(cls, aliases: Optional[List[str]], name: str) -> List[str]:
        result = []
        seen = set()
        for alias in [name, *(aliases if isinstance(aliases, list) else [])]:
            normalized = cls._normalize(alias)
            if normalized and normalized not in seen:
                result.append(" ".join(alias.split()))
                seen.add(normalized)
        return result

    def add_entity(self, name: str, entity_type: str = "unknown",
                   aliases: List[str] = None, metadata: Dict = None) -> None:
        """Adiciona ou atualiza uma entidade sem alterar os argumentos recebidos."""
        key = self._normalize(name)
        if not key:
            if self.logger:
                self.logger.warning("[EntityTracker] Nome de entidade inválido; ignorando")
            return

        clean_name = " ".join(name.split())
        clean_aliases = self._clean_aliases(aliases, clean_name)
        clean_metadata = deepcopy(metadata) if isinstance(metadata, dict) else {}
        now = datetime.now().isoformat()
        existing_key = self._find_key(clean_name)

        if existing_key is not None:
            entity = self._entities[existing_key]
            entity["last_mentioned"] = now
            entity["mention_count"] = entity.get("mention_count", 0) + 1
            entity["aliases"] = self._clean_aliases(
                entity.get("aliases", []) + clean_aliases, entity["name"]
            )
            entity["metadata"].update(clean_metadata)
            if entity.get("type") == "unknown" and entity_type != "unknown":
                entity["type"] = entity_type
            if self.logger:
                self.logger.debug(f"[EntityTracker] Entidade atualizada: {entity['name']}")
            return

        self._entities[key] = {
            "name": clean_name,
            "type": entity_type if isinstance(entity_type, str) else "unknown",
            "aliases": clean_aliases,
            "metadata": clean_metadata,
            "first_mentioned": now,
            "last_mentioned": now,
            "mention_count": 1,
        }
        if self.logger:
            self.logger.debug(f"[EntityTracker] Nova entidade: {clean_name}")

    def get_entity(self, name: str) -> Optional[Dict]:
        """Busca por nome ou alias e retorna cópia independente."""
        key = self._find_key(name)
        return deepcopy(self._entities[key]) if key is not None else None

    def get_entities(self, limit: int = 10) -> List[Dict]:
        """Retorna entidades ordenadas por frequência e recência."""
        if not isinstance(limit, int) or limit <= 0:
            return []
        entities = sorted(
            self._entities.values(),
            key=lambda entity: (
                entity.get("mention_count", 0),
                entity.get("last_mentioned", ""),
            ),
            reverse=True,
        )
        return deepcopy(entities[:limit])

    def get_active_entities(self, limit: int = 5) -> List[Dict]:
        """Retorna as entidades mencionadas mais recentemente."""
        if not isinstance(limit, int) or limit <= 0:
            return []
        entities = sorted(
            self._entities.values(),
            key=lambda entity: entity.get("last_mentioned", ""),
            reverse=True,
        )
        return deepcopy(entities[:limit])

    def find_by_alias(self, alias: str) -> Optional[Dict]:
        """Busca uma entidade por nome ou apelido."""
        return self.get_entity(alias)

    def add_alias(self, entity_name: str, alias: str) -> bool:
        """Adiciona um apelido a uma entidade identificada por nome ou alias."""
        key = self._find_key(entity_name)
        if key is None or not self._normalize(alias):
            return False
        entity = self._entities[key]
        if any(self._normalize(item) == self._normalize(alias)
               for item in entity.get("aliases", [])):
            return False
        # Evita associar um apelido já pertencente a outra entidade.
        owner_key = self._find_key(alias)
        if owner_key is not None and owner_key != key:
            return False
        entity["aliases"].append(" ".join(alias.split()))
        return True

    def clear(self) -> None:
        """Limpa todas as entidades."""
        self._entities.clear()
        if self.logger:
            self.logger.debug("[EntityTracker] Entidades limpas")

    def get_status(self) -> Dict:
        """Retorna um resumo do rastreador."""
        return {
            "total_entities": len(self._entities),
            "entities": list(self._entities.keys()),
        }
