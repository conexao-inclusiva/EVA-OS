# -*- coding: utf-8 -*-
"""Reconhecimento conservador de relações explícitas para a Etapa 12.5.
Não faz inferências, não acessa SQLite e não chama LLM.
"""
import re
from src.memory.fact_learning import normalize, strip_eva


def extract(text):
    phrase = strip_eva(text).strip().rstrip('.!')
    if '?' in text or '\n' in phrase or len(phrase) > 180:
        return None
    norm = normalize(phrase)
    if re.search(r'\b(talvez|acho|penso|pensando|planejo|pretendo|gostaria|queria|se eu|nao|nunca|futuramente|vou|era|tinha)\b', norm):
        return None
    m = re.fullmatch(r'(?:minha|meu)\s+(?P<vehicle>[\wÀ-ÿ-]{2,40})\s+(?:tem|possui)\s+(?:um\s+|uma\s+)?(?P<field>motor|cor|ano|modelo)\s+(?P<value>[\wÀ-ÿ .-]{1,70})', phrase, re.I)
    if m:
        val = m.group('value').strip()
        if normalize(val) in {'um', 'uma', 'novo', 'nao sei'}:
            return None
        return {'subject': normalize(m.group('vehicle')), 'relation': normalize(m.group('field')), 'object': val}
    m = re.fullmatch(r'(?:eu\s+)?(?:tamb[eé]m\s+tenho|possuo\s+tamb[eé]m)\s+(?:um|uma)\s+(?P<vehicle>[\wÀ-ÿ -]{2,70})', phrase, re.I)
    if m:
        return {'subject': 'usuario', 'relation': 'possui', 'object': m.group('vehicle').strip()}
    return None


def question(text):
    norm = normalize(strip_eva(text).strip(' .?!'))
    m = re.fullmatch(r'(?:qual e|qual)\s+(?:o|a)\s+(motor|cor|ano|modelo)\s+d[ao]\s+(?:meu|minha)\s+([\w -]{2,40})', norm)
    if m:
        return (m.group(2).strip(), m.group(1), 'O {} registrado é {{}}.'.format(m.group(1)))
    if norm in {'quais carros eu tenho', 'quais veiculos eu tenho', 'que outros carros eu tenho'}:
        return ('usuario', 'possui', 'Você também registrou estes veículos: {}.')
    return None
