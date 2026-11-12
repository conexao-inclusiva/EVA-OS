# -*- coding: utf-8 -*-
"""EVA-OS 12.7.1: aprendizado familiar explícito, múltiplos filhos e correção confirmada."""
import re
import sqlite3
import unicodedata
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def norm(s):
    s = unicodedata.normalize('NFKD', str(s).casefold())
    return ' '.join(''.join(c for c in s if not unicodedata.combining(c)).split())


def clean(text):
    return re.sub(r'^\s*(?:eva|ei eva|oi eva)\s*[,!:]?\s*', '', text, flags=re.I).strip().rstrip('.!')


SINGULAR = {'pai', 'mae', 'responsavel', 'esposa', 'marido'}
ALLOWED = SINGULAR | {'filho', 'filha', 'irmao', 'irma'}
KIN = {'filho': 'filho', 'filha': 'filha', 'pai': 'pai', 'mae': 'mae',
       'irmao': 'irmao', 'irma': 'irma'}
NAME = r'[\wÀ-ÿ][\wÀ-ÿ -]{1,55}?'



def _extract_extended_family(text):
    if not isinstance(text, str):
        return None

    s = clean(text)

    if not s or len(s) > 160 or any(c in s for c in ("?", "\n", ",", ";")):
        return None

    if re.search(
        r"\b(?:nao|nunca|talvez|acho|penso|seria|fosse|era|tinha|corrija|errado)\b",
        norm(s)
    ):
        return None

    m = re.fullmatch(
        rf"(?P<person>{NAME})\s+(?:\u00e9|e)\s+"
        rf"(?:meu\s+(?P<male>marido|esposo)|minha\s+(?P<female>esposa))",
        s, re.I
    )
    if m:
        return {
            "subject": "usuario",
            "relation": "marido" if m.group("male") else "esposa",
            "object": m.group("person").strip()
        }

    m = re.fullmatch(
        rf"(?P<person>{NAME})\s+(?:\u00e9|e)\s+"
        rf"(?P<relation>pai|m\u00e3e|mae|filho|filha|irm\u00e3o|irmao|irm\u00e3|irma)\s+"
        rf"(?:do|da|de)\s+(?P<subject>{NAME})",
        s, re.I
    )
    if m:
        person = m.group("person").strip()
        subject = m.group("subject").strip()

        if norm(person) == norm(subject):
            return None

        return {
            "subject": "pessoa:" + norm(subject),
            "relation": norm(m.group("relation")),
            "object": person
        }

    return None


def extract(text):
    s = clean(text)
    if not s or '?' in text or '\n' in s or len(s) > 160:
        return None
    if re.search(r'\b(talvez|acho|penso|planejo|pretendo|gostaria|queria|nao|nunca|seria|fosse|era|tinha)\b', norm(s)):
        return None
    m = re.fullmatch(rf'(?P<person>{NAME})\s+(?:é|e)\s+meu\s+(?P<rel>filho|pai|irmão|irmao)', s, re.I)
    if not m:
        m = re.fullmatch(rf'(?P<person>{NAME})\s+(?:é|e)\s+minha\s+(?P<rel>filha|mãe|mae|irmã|irma)', s, re.I)
    if m:
        return {'subject': 'usuario', 'relation': norm(m['rel']), 'object': m['person'].strip()}
    m = re.fullmatch(rf'(?:meu|minha)\s+(?P<rel>filho|filha|pai|mãe|mae|irmão|irmao|irmã|irma)\s+se\s+chama\s+(?P<person>{NAME})', s, re.I)
    if m:
        return {'subject': 'usuario', 'relation': norm(m['rel']), 'object': m['person'].strip()}
    m = re.fullmatch(rf'(?P<person>{NAME})\s+(?:é|e)\s+respons[aá]vel\s+pel[oa]\s+projeto\s+(?P<project>{NAME})', s, re.I)
    if m:
        return {'subject': 'projeto:' + norm(m['project']), 'relation': 'responsavel', 'object': m['person'].strip()}
    return _extract_extended_family(text)


def removal(text):
    """Só solicita desativação explícita; a confirmação acontece no Brain."""
    s = clean(text)
    if '?' in text or '\n' in s or len(s) > 160:
        return None
    m = re.fullmatch(rf'(?:remova|exclua|apague)\s+(?:o\s+registro\s+de\s+)?me[uo]\s+(?P<rel>filho|filha|pai|mãe|mae|irmão|irmao|irmã|irma)\s+(?P<person>{NAME})', s, re.I)
    if m:
        return {'subject': 'usuario', 'relation': norm(m['rel']), 'object': m['person'].strip()}
    return None



def question(text):
    s = norm(clean(text).strip(' ?'))

    q = {
        'quem e meu filho': ('usuario', 'filho', 'Seu filho registrado \u00e9 {}.'),
        'qual e o nome do meu filho': ('usuario', 'filho', 'Seu filho registrado \u00e9 {}.'),
        'quem e minha filha': ('usuario', 'filha', 'Sua filha registrada \u00e9 {}.'),
        'qual e o nome da minha filha': ('usuario', 'filha', 'Sua filha registrada \u00e9 {}.'),
        'quem e meu pai': ('usuario', 'pai', 'Seu pai registrado \u00e9 {}.'),
        'quem e minha mae': ('usuario', 'mae', 'Sua m\u00e3e registrada \u00e9 {}.'),
        'quem sao meus filhos': ('usuario', 'filhos', 'Seus filhos registrados s\u00e3o {}.'),
        'quais sao meus filhos': ('usuario', 'filhos', 'Seus filhos registrados s\u00e3o {}.'),
        'quem sao minhas filhas': ('usuario', 'filha', 'Suas filhas registradas s\u00e3o {}.'),
        'quem e meu irmao': ('usuario', 'irmao', 'Seu irm\u00e3o registrado \u00e9 {}.'),
        'quem e minha irma': ('usuario', 'irma', 'Sua irm\u00e3 registrada \u00e9 {}.'),
        'quem e minha esposa': ('usuario', 'esposa', 'Sua esposa registrada \u00e9 {}.'),
        'quem e meu marido': ('usuario', 'marido', 'Seu marido registrado \u00e9 {}.'),
    }

    if s in q:
        return q[s]

    m = re.fullmatch(
        r'quem e (?:o |a )?(pai|mae|filho|filha|irmao|irma) '
        r'(?:do|da|de) ([\w -]{2,55})',
        s
    )
    if m:
        rel, person = m.groups()
        labels = {
            'pai': 'Pai',
            'mae': 'M\u00e3e',
            'filho': 'Filho',
            'filha': 'Filha',
            'irmao': 'Irm\u00e3o',
            'irma': 'Irm\u00e3',
        }
        return (
            'pessoa:' + norm(person),
            rel,
            labels[rel] + ' registrado(a): {}.'
        )

    m = re.fullmatch(r'quem e responsavel pelo projeto ([\w -]{2,55})', s)
    if m:
        return (
            'projeto:' + m[1].strip(),
            'responsavel',
            'Respons\u00e1vel registrado pelo projeto: {}.'
        )

    return None



class FamilyRelations:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS family_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
                subject TEXT NOT NULL, relation TEXT NOT NULL, object TEXT NOT NULL,
                valid_from TEXT NOT NULL, valid_to TEXT)""")
            db.execute('CREATE INDEX IF NOT EXISTS idx_family_active ON family_relations(user_id, subject, relation, valid_to)')

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def active(self, user, subject, relation):
        if relation not in ALLOWED:
            raise ValueError('Relação não permitida')
        with closing(self._connect()) as db:
            return [dict(r) for r in db.execute("""SELECT * FROM family_relations WHERE
                user_id=? AND subject=? AND relation=? AND valid_to IS NULL ORDER BY id""",
                (user, subject, relation))]

    def save(self, user, subject, relation, obj, expected_previous=None):
        if relation not in ALLOWED or not all(isinstance(x, str) and x.strip() for x in (user, subject, obj)):
            raise ValueError('Relação inválida')
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute("""SELECT object FROM family_relations WHERE user_id=? AND subject=?
                AND relation=? AND valid_to IS NULL""", (user, subject, relation)).fetchall()
            current = {r['object'] for r in rows}
            if any(norm(v) == norm(obj) for v in current):
                db.rollback()
                return 'already_known'
            if relation in SINGULAR and current:
                if expected_previous is None or current != set(expected_previous):
                    db.rollback()
                    return 'needs_confirmation'
                db.execute("""UPDATE family_relations SET valid_to=? WHERE user_id=? AND subject=?
                    AND relation=? AND valid_to IS NULL""", (now, user, subject, relation))
            db.execute("""INSERT INTO family_relations(user_id,subject,relation,object,valid_from,valid_to)
                VALUES(?,?,?,?,?,NULL)""", (user, subject, relation, obj, now))
            db.commit()
            return 'saved'

    def deactivate_confirmed(self, user, subject, relation, obj, expected_ids):
        """Desativa somente o registro exato confirmado; preserva histórico e impede corrida."""
        if relation not in ALLOWED or not expected_ids:
            return 'not_found'
        with closing(self._connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute("""SELECT id, object FROM family_relations WHERE user_id=? AND subject=?
                AND relation=? AND valid_to IS NULL""", (user, subject, relation)).fetchall()
            matching = [r for r in rows if norm(r['object']) == norm(obj)]
            ids = sorted(r['id'] for r in matching)
            if not ids or ids != sorted(expected_ids):
                db.rollback()
                return 'changed'
            now = datetime.now(timezone.utc).isoformat()
            for ident in ids:
                db.execute("""UPDATE family_relations SET valid_to=? WHERE id=? AND user_id=?
                    AND valid_to IS NULL""", (now, ident, user))
            db.commit()
            return 'deactivated'

    def history(self, user, subject, relation):
        with closing(self._connect()) as db:
            return [dict(r) for r in db.execute("""SELECT * FROM family_relations WHERE
                user_id=? AND subject=? AND relation=? ORDER BY id""", (user, subject, relation))]
