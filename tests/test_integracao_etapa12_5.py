# -*- coding: utf-8 -*-
"""Execute no projeto: python -m pytest tests/test_integracao_etapa12_5.py -v"""
import asyncio
from pathlib import Path
from src.memory.relational_memory import RelationalMemory
from src.memory import relational_learning


def test_extracao_conservadora():
    assert relational_learning.extract('Minha Meriva tem motor 1.8')['relation'] == 'motor'
    assert relational_learning.extract('Também tenho um Chevrolet Corsa 1999')['relation'] == 'possui'
    for sentence in ('Talvez minha Meriva tenha motor 2.0', 'Minha Meriva não tem motor 1.8',
                     'Quero comprar um Corsa', 'Qual o motor da minha Meriva?'):
        assert relational_learning.extract(sentence) is None


def test_relacoes_e_confirmacao(tmp_path):
    db = RelationalMemory(tmp_path / 'relacoes.db')
    assert db.save_confirmed('admin', 'meriva', 'motor', '1.8') == 'saved'
    assert db.propose('admin', 'meriva', 'motor', '2.0') == 'needs_confirmation'
    assert db.save_confirmed('admin', 'meriva', 'motor', '2.0') == 'needs_confirmation'
    assert db.active('admin', 'meriva', 'motor')[0]['object'] == '1.8'
    assert db.save_confirmed('admin', 'usuario', 'possui', 'Chevrolet Corsa 1999') == 'saved'
    assert db.save_confirmed('admin', 'usuario', 'possui', 'Chevrolet Meriva 2004') == 'saved'
    assert len(db.active('admin', 'usuario', 'possui')) == 2
    assert not db.active('outro', 'usuario', 'possui')
    assert db.save_confirmed('admin', 'meriva', 'motor', '2.0', expected_previous=['1.8']) == 'saved'
    assert len(db.history('admin', 'meriva', 'motor')) == 2
    reopened = RelationalMemory(tmp_path / 'relacoes.db')
    assert reopened.active('admin', 'meriva', 'motor')[0]['object'] == '2.0'


def test_consulta_exata():
    assert relational_learning.question('Qual é o motor da minha Meriva?') == ('meriva', 'motor', 'O motor registrado é {}.')
    assert relational_learning.question('Quais carros eu tenho?')[1] == 'possui'
