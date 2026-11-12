import asyncio
from pathlib import Path
from src.memory import family_relations as fr
from src.consciousness.brain import Brain


def test_extracao_segura():
    assert fr.extract('Lucas é meu filho') == {'subject':'usuario','relation':'filho','object':'Lucas'}
    assert fr.extract('Marina é responsável pelo projeto Aurora') == {'subject':'projeto:aurora','relation':'responsavel','object':'Marina'}
    assert fr.extract('Talvez Lucas é meu filho') is None
    assert fr.extract('Lucas é meu filho?') is None


def test_persistencia_e_isolamento(tmp_path):
    path = tmp_path / 'familia.db'
    db = fr.FamilyRelations(path)
    assert db.save('admin','usuario','filho','Lucas') == 'saved'
    assert db.save('admin','usuario','filho','Pedro') == 'saved'
    assert db.save('admin','usuario','filho','Lucas') == 'already_known'
    assert not db.active('outro','usuario','filho')
    assert len(fr.FamilyRelations(path).active('admin','usuario','filho')) == 2


def test_contradicao_e_historico(tmp_path):
    db = fr.FamilyRelations(tmp_path / 'familia.db')
    assert db.save('admin','usuario','pai','Roberto') == 'saved'
    assert db.save('admin','usuario','pai','Carlos') == 'needs_confirmation'
    assert db.active('admin','usuario','pai')[0]['object'] == 'Roberto'
    assert db.save('admin','usuario','pai','Carlos', expected_previous=['Roberto']) == 'saved'
    assert db.active('admin','usuario','pai')[0]['object'] == 'Carlos'
    assert len(db.history('admin','usuario','pai')) == 2


def test_brain_consulta_local(tmp_path):
    brain = object.__new__(Brain)
    brain.family_relations = fr.FamilyRelations(tmp_path / 'familia.db')
    assert brain._resolve_family_fact('Quem é meu pai?', 'admin') is None
    brain.family_relations.save('admin','usuario','pai','Roberto')
    assert 'Roberto' in brain._resolve_family_fact('Quem é meu pai?', 'admin')
    assert brain._resolve_family_fact('Qual é meu carro atual?', 'admin') is None


def test_brain_aprendizado_e_confirmacao(tmp_path):
    from unittest.mock import Mock
    brain = object.__new__(Brain)
    brain.family_relations = fr.FamilyRelations(tmp_path / 'familia.db')
    brain._pending_family_corrections = {}
    brain.logger = Mock()
    assert 'Registrei' in asyncio.run(brain._try_family_learning('Roberto é meu pai', 'admin'))
    assert 'confirma' in asyncio.run(brain._try_family_learning('Carlos é meu pai', 'admin'))
    assert 'mantive' in asyncio.run(brain._handle_pending_family_correction('Não.', 'admin'))
    assert brain.family_relations.active('admin','usuario','pai')[0]['object'] == 'Roberto'
    assert 'confirma' in asyncio.run(brain._try_family_learning('Carlos é meu pai', 'admin'))
    assert 'Atualizei' in asyncio.run(brain._handle_pending_family_correction('Sim.', 'admin'))
    assert brain.family_relations.active('admin','usuario','pai')[0]['object'] == 'Carlos'
