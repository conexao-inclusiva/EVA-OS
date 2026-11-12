"""Memória familiar da EVA: árvore genealógica com persistência JSON."""

import copy
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.kernel.events import EventBus


class FamilyMemory:
    """Mantém membros e vínculos familiares no formato existente de tree.json."""

    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self._running = False
        self._family_tree: Dict[str, Any] = self._empty_tree()
        data_path = config.get('paths.data', './data')
        if isinstance(data_path, dict):
            data_path = data_path.get('data', './data')
        self._family_path = Path(data_path) / 'family' / 'tree.json'
        self._family_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger.info('[FamilyMemory] Inicializado')

    @staticmethod
    def _empty_tree() -> Dict[str, Any]:
        return {'members': {}, 'relationships': [], 'last_updated': None}

    @staticmethod
    def _id(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Nome do familiar deve ser uma string não vazia')
        return '_'.join(name.strip().casefold().split())

    def _lookup_id(self, name: Optional[str]) -> Optional[str]:
        if not isinstance(name, str) or not name.strip():
            return None
        key = self._id(name)
        if key in self._family_tree['members']:
            return key
        for member_id, member in self._family_tree['members'].items():
            if self._id(member.get('name', member_id)) == key:
                return member_id
        return None

    async def initialize(self) -> None:
        await self._load_tree()
        self._running = True
        self.logger.info('[FamilyMemory] Inicializado e carregado')

    def add_member(self, name: str, relation: str, parent: str = None,
                   spouse: str = None) -> None:
        """Cadastra/atualiza familiar e salva imediatamente, sem exigir await."""
        member_id = self._id(name)
        if not isinstance(relation, str):
            raise ValueError('Relação deve ser texto')
        members = self._family_tree['members']
        old = members.get(member_id, {})
        old_parent = self._lookup_id(old.get('parent'))
        parent_id = self._lookup_id(parent) if parent else None
        if parent and parent_id is None:
            self.logger.warning('[FamilyMemory] Pai/mãe não cadastrado: %s', parent)
        if parent_id == member_id:
            raise ValueError('Uma pessoa não pode ser seu próprio pai/mãe')
        children = old.get('children', [])
        if not isinstance(children, list):
            children = []
        members[member_id] = {
            **old,
            'name': name.strip(),
            'relation': relation.strip(),
            'parent': parent_id or (parent.strip() if parent else old.get('parent')),
            'spouse': self._lookup_id(spouse) or (spouse.strip() if spouse else old.get('spouse')),
            'children': children,
            'added_at': old.get('added_at') or datetime.now().isoformat(),
        }
        if old_parent and old_parent != parent_id:
            siblings = members[old_parent].get('children', [])
            members[old_parent]['children'] = [c for c in siblings if c != member_id]
        if parent_id:
            parent_children = members[parent_id].setdefault('children', [])
            if member_id not in parent_children:
                parent_children.append(member_id)
        self._write_tree()
        self.logger.info('[FamilyMemory] Membro registrado: %s', name)

    def get_member(self, name: str) -> Optional[Dict[str, Any]]:
        member_id = self._lookup_id(name)
        member = self._family_tree['members'].get(member_id) if member_id else None
        return copy.deepcopy(member) if member is not None else None

    def get_family_tree(self) -> Dict[str, Any]:
        return copy.deepcopy(self._family_tree)

    def get_children(self, parent_name: str) -> List[str]:
        parent = self.get_member(parent_name)
        return list(parent.get('children', [])) if parent else []

    def get_parents(self, child_name: str) -> List[str]:
        child = self.get_member(child_name)
        return [child['parent']] if child and child.get('parent') else []

    def get_relation(self, name1: str, name2: str) -> Optional[str]:
        """Relação de name1 em relação a name2, quando registrada explicitamente."""
        id1, id2 = self._lookup_id(name1), self._lookup_id(name2)
        if not id1 or not id2 or id1 == id2:
            return None
        members = self._family_tree['members']
        m1, m2 = members[id1], members[id2]
        if self._lookup_id(m1.get('parent')) == id2:
            return 'filho(a)'
        if self._lookup_id(m2.get('parent')) == id1:
            return 'pai/mãe'
        if self._lookup_id(m1.get('spouse')) == id2 or self._lookup_id(m2.get('spouse')) == id1:
            return 'cônjuge'
        p1 = self._lookup_id(m1.get('parent'))
        p2 = self._lookup_id(m2.get('parent'))
        if p1 and p1 == p2:
            return 'irmão(ã)'
        for relationship in self._family_tree.get('relationships', []):
            if not isinstance(relationship, dict):
                continue
            a = relationship.get('from', relationship.get('person1'))
            b = relationship.get('to', relationship.get('person2'))
            if self._lookup_id(a) == id1 and self._lookup_id(b) == id2:
                return relationship.get('relation', relationship.get('type'))
        return None

    def search(self, query: str) -> List[Dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            return []
        term = query.strip().casefold()
        return [copy.deepcopy(member) for member in self._family_tree['members'].values()
                if term in member.get('name', '').casefold()]

    def format_tree(self) -> str:
        members = self._family_tree['members']
        lines = ['ÁRVORE GENEALÓGICA', '=' * 30]
        for member in members.values():
            lines.append(f"\n{member.get('name', 'Desconhecido')} ({member.get('relation', '')})")
            parent = member.get('parent')
            if parent:
                parent_id = self._lookup_id(parent)
                parent_name = members[parent_id].get('name', parent) if parent_id else parent
                lines.append(f'  Filho(a) de: {parent_name}')
            children = member.get('children', [])
            if isinstance(children, list) and children:
                names = [members[c].get('name', c) if c in members else c for c in children]
                lines.append('  Filhos: ' + ', '.join(names))
        return '\n'.join(lines)

    async def _load_tree(self) -> None:
        if not self._family_path.exists():
            return
        try:
            with self._family_path.open('r', encoding='utf-8') as stream:
                loaded = json.load(stream)
            if not isinstance(loaded, dict) or not isinstance(loaded.get('members'), dict):
                raise ValueError('Formato inválido de árvore familiar')
            if not isinstance(loaded.get('relationships', []), list):
                raise ValueError('Campo relationships inválido')
            if any(not isinstance(m, dict) for m in loaded['members'].values()):
                raise ValueError('Registro de familiar inválido')
            self._family_tree = {**self._empty_tree(), **loaded}
        except (OSError, ValueError, TypeError) as exc:
            self.logger.error('[FamilyMemory] Falha ao carregar árvore; arquivo preservado: %s', exc)
            raise

    def _write_tree(self) -> None:
        """Grava com substituição atômica para não truncar o arquivo existente."""
        updated = datetime.now().isoformat()
        snapshot = copy.deepcopy(self._family_tree)
        snapshot['last_updated'] = updated
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=str(self._family_path.parent),
                                             prefix='.tree-', suffix='.tmp', delete=False) as stream:
                temp_path = stream.name
                json.dump(snapshot, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self._family_path)
            self._family_tree['last_updated'] = updated
        except (OSError, TypeError, ValueError) as exc:
            self.logger.error('[FamilyMemory] Falha ao salvar árvore: %s', exc)
            raise
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    async def _save_tree(self) -> None:
        self._write_tree()

    async def shutdown(self) -> None:
        await self._save_tree()
        self._running = False
        self.logger.info('[FamilyMemory] Desligado')

    async def health_check(self) -> dict:
        return {'status': 'running' if self._running else 'stopped',
                'members': len(self._family_tree['members'])}
