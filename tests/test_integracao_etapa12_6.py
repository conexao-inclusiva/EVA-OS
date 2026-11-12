# -*- coding: utf-8 -*-
"""Testes isolados da consulta unificada, sem tocar nos bancos da EVA."""
import asyncio
from unittest.mock import Mock
from src.consciousness.brain import Brain

class LongTermFake:
    def __init__(self, facts):
        self.facts = facts
    async def get_all_facts(self, user_id):
        return self.facts.get(user_id, [])

class RelationalFake:
    def __init__(self, facts):
        self.facts = facts
    def active(self, user_id, subject, relation):
        assert (subject, relation) == ('usuario', 'possui')
        return [{'object': v} for v in self.facts.get(user_id, [])]

def brain_for_test(longterm, relational):
    brain = object.__new__(Brain)
    brain._modules = {'long_term_memory': LongTermFake(longterm)}
    brain.relational_memory = RelationalFake(relational)
    return brain

def fact(value):
    return {'subject': 'veiculo', 'relation': 'carro_atual',
            'object': value, 'source': 'ensinado_geral_explicitamente'}

def ask(brain, text, user='admin'):
    return asyncio.run(brain._resolve_unified_vehicles(text, user))

def test_unifica_carro_atual_e_outro():
    b = brain_for_test({'admin': [fact('Chevrolet Meriva 2004')]},
                       {'admin': ['Chevrolet Corsa 1999']})
    answer = ask(b, 'Quais carros eu tenho?')
    assert 'Chevrolet Meriva 2004' in answer
    assert 'Chevrolet Corsa 1999' in answer
    assert 'carro atual' in answer

def test_evitar_duplicata():
    b = brain_for_test({'admin': [fact('Chevrolet Meriva 2004')]},
                       {'admin': ['chevrolet meriva 2004', 'Chevrolet Corsa 1999']})
    answer = ask(b, 'Quais veículos eu tenho?')
    assert answer.lower().count('meriva') == 1
    assert 'Corsa' in answer

def test_isolamento_usuarios():
    b = brain_for_test({'admin': [fact('Chevrolet Meriva 2004')]},
                       {'admin': ['Chevrolet Corsa 1999']})
    assert ask(b, 'Quais carros eu tenho?', 'outro') is None

def test_sem_dados_nao_inventa():
    b = brain_for_test({}, {})
    assert ask(b, 'Quais carros eu tenho?') is None

def test_pergunta_nao_relacionada_nao_intercepta():
    b = brain_for_test({'admin': [fact('Chevrolet Meriva 2004')]}, {})
    assert ask(b, 'Qual é meu carro atual?') is None

def test_conflito_nao_escolhe_atual():
    b = brain_for_test({'admin': [fact('Meriva'), fact('Corsa')]},
                       {'admin': ['Chevrolet Corsa 1999']})
    answer = ask(b, 'Quais carros eu tenho?')
    assert 'Chevrolet Corsa 1999' in answer
    assert 'carro atual' not in answer
