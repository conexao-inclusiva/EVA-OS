# -*- coding: utf-8 -*-
"""Testes isolados: banco temporário, sem escrever no banco real da EVA."""
import ast
import importlib.util
from pathlib import Path
import tempfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT / 'src' / 'memory' / 'family_relations.py'
BRAIN = ROOT / 'src' / 'consciousness' / 'brain.py'

@pytest.fixture
def fm():
    spec = importlib.util.spec_from_file_location('family_relations_test_1271', FAMILY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@pytest.fixture
def store(fm, tmp_path):
    return fm.FamilyRelations(tmp_path / 'isolated.db')

def test_frases_explicitas(fm):
    assert fm.extract('Meu filho se chama Pessoa A.') == {'subject':'usuario','relation':'filho','object':'Pessoa A'}
    assert fm.extract('Minha filha se chama Pessoa B.')['relation'] == 'filha'
    assert fm.extract('Pessoa A é meu filho.')['object'] == 'Pessoa A'

def test_nao_inventa(fm):
    for text in ('Talvez meu filho se chama Pessoa A', 'Meu filho se chama Pessoa A?', 'Meu filho não se chama Pessoa A'):
        assert fm.extract(text) is None

def test_multiplos_e_isolamento(store):
    assert store.save('a','usuario','filho','Pessoa A') == 'saved'
    assert store.save('a','usuario','filho','Pessoa B') == 'saved'
    assert store.save('a','usuario','filha','Pessoa C') == 'saved'
    assert len(store.active('a','usuario','filho')) == 2
    assert store.active('b','usuario','filho') == []

def test_remocao_exige_confirmacao_e_preserva_historico(store, fm):
    store.save('a','usuario','filho','Pessoa A')
    assert fm.removal('Remova meu filho Pessoa A.')['object'] == 'Pessoa A'
    row = store.active('a','usuario','filho')[0]
    assert store.deactivate_confirmed('a','usuario','filho','Pessoa A',[row['id']+100]) == 'changed'
    assert len(store.active('a','usuario','filho')) == 1
    assert store.deactivate_confirmed('a','usuario','filho','Pessoa A',[row['id']]) == 'deactivated'
    assert store.active('a','usuario','filho') == []
    assert len(store.history('a','usuario','filho')) == 1
    assert store.history('a','usuario','filho')[0]['valid_to'] is not None

def test_correcao_singular(store):
    assert store.save('a','usuario','pai','Pessoa A') == 'saved'
    assert store.save('a','usuario','pai','Pessoa B') == 'needs_confirmation'
    assert store.save('a','usuario','pai','Pessoa B',expected_previous=['Pessoa A']) == 'saved'
    assert store.active('a','usuario','pai')[0]['object'] == 'Pessoa B'

def test_pergunta_filhos(fm):
    assert fm.question('Quem são meus filhos?')[1] == 'filhos'
    assert fm.question('Qual é o nome do meu filho?')[1] == 'filho'

def test_brain_preserva_fluxos():
    code = BRAIN.read_text(encoding='utf-8')
    tree = ast.parse(code)
    cls = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name == 'Brain')
    names = {n.name for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    assert {'_try_family_removal','_resolve_family_fact','_resolve_unified_vehicles',
            '_resolve_relational_fact','_resolve_persistent_fact','_resolve_general_fact',
            '_try_family_learning','_handle_pending_family_correction'} <= names
