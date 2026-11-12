# -*- coding: utf-8 -*-
"""Regras conservadoras de fatos gerais; sem LLM e sem acesso ao banco.

Retorna apenas afirmacoes explicitas. Perguntas, planos, negacoes e
hipoteses nao viram fatos permanentes.
"""
import re
import unicodedata


def normalize(text):
    text = unicodedata.normalize('NFKD', str(text).casefold())
    return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).split())


def strip_eva(text):
    return re.sub(r'^\s*(?:eva|ei eva|oi eva)\s*[,!:]?\s*', '', text, flags=re.I).strip()


def extract(text):
    statement = strip_eva(text).rstrip(' .!')
    if '?' in text or '\n' in statement or len(statement) > 180:
        return None
    norm = normalize(statement)
    if re.search(r'\b(talvez|acho|penso|pensando|planejo|pretendo|gostaria|queria|se eu|quando eu|nao|nunca|possivelmente|provavelmente|futuramente|vou comprar|quero comprar|era|tinha)\b', norm):
        return None
    statement = re.sub(r'^(?:lembre(?:-se)?(?: de)? que|anote que|guarde que)\s*[:,]?\s*', '', statement, flags=re.I)
    patterns = [
        (r'^meu carro (?:atual )?(?:e|é) (?:um |uma )?(?P<value>.+)$', 'veiculo', 'carro_atual'),
        (r'^eu tenho (?:um|uma) carro (?P<value>.+)$', 'veiculo', 'carro_atual'),
        (r'^meu projeto (?P<subject>[\wÀ-ÿ -]{2,55}) (?:tem como objetivo|serve para) (?P<value>.+)$', 'projeto', 'objetivo'),
        (r'^eu prefiro (?P<value>.+)$', 'preferencia', 'preferencia_geral'),
    ]
    for pattern, category, relation in patterns:
        match = re.fullmatch(pattern, statement, re.I)
        if not match:
            continue
        value = match.group('value').strip().strip('"“”')
        if len(value) < 3 or len(value) > 100 or normalize(value) in {'carro', 'novo carro', 'um carro', 'alguma coisa'}:
            return None
        if re.search(r'\b(talvez|acho|pretendo|planejo|gostaria|queria|nao|nunca)\b', normalize(value)):
            return None
        subject = normalize(match.group('subject')) if 'subject' in match.groupdict() else category
        return {'subject': subject, 'relation': relation, 'object': value, 'category': category}
    return None


def question(text):
    statement = normalize(strip_eva(text).strip(' .?!'))
    if statement in {'qual e meu carro atual', 'qual e o meu carro atual', 'que carro eu tenho'}:
        return ('veiculo', 'carro_atual', 'O seu carro atual é {}.')
    if statement in {'qual e minha preferencia', 'qual e a minha preferencia'}:
        return ('preferencia', 'preferencia_geral', 'Você me disse que prefere {}.')
    match = re.fullmatch(r'qual e o objetivo do meu projeto ([\w -]{2,55})', statement)
    if match:
        return (match.group(1).strip(), 'objetivo', 'O objetivo do seu projeto é {}.')
    return None
