# -*- coding: utf-8 -*-
"""EVA-OS Etapa 12.4: base relacional aditiva, sem migrar fatos legados.

Uso futuro pelo Brain, após integração e testes. Nenhum dado existente é apagado.
"""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

SINGLE = frozenset({'motor', 'cor', 'ano', 'modelo', 'objetivo', 'carro_atual'})
MULTI = frozenset({'possui', 'participa', 'componente', 'interesse'})
ALLOWED = SINGLE | MULTI


class RelationalMemory:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute('''CREATE TABLE IF NOT EXISTS relational_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                relation TEXT NOT NULL,
                object TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT,
                created_at TEXT NOT NULL
            )''')
            db.execute('''CREATE INDEX IF NOT EXISTS idx_relational_active
                ON relational_facts(user_id, subject, relation, valid_to)''')

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _validate(user_id, subject, relation, obj):
        if not all(isinstance(x, str) and x.strip() for x in (user_id, subject, relation, obj)):
            raise ValueError('Identificadores e valor não podem estar vazios')
        if relation not in ALLOWED:
            raise ValueError('Relação não cadastrada: ' + relation)

    def active(self, user_id, subject, relation):
        if relation not in ALLOWED:
            raise ValueError('Relação não cadastrada')
        with closing(self._connect()) as db:
            rows = db.execute('''SELECT * FROM relational_facts
                WHERE user_id=? AND subject=? AND relation=? AND valid_to IS NULL
                ORDER BY id''', (user_id, subject, relation)).fetchall()
            return [dict(r) for r in rows]

    def propose(self, user_id, subject, relation, obj):
        """Não escreve. Indica se exige confirmação humana."""
        self._validate(user_id, subject, relation, obj)
        existing = self.active(user_id, subject, relation)
        if any(r['object'].casefold() == obj.casefold() for r in existing):
            return 'already_known'
        if relation in SINGLE and existing:
            return 'needs_confirmation'
        return 'new'

    def save_confirmed(self, user_id, subject, relation, obj, *, source='usuario_confirmado',
                       confidence=0.95, expected_previous=None):
        """Grava transacionalmente; nunca sobrescreve silenciosamente.

        Para relação SINGLE com valor existente, exige lista exata de valores anteriores
        aprovada pelo usuário (expected_previous). Histórico é preservado via valid_to.
        """
        self._validate(user_id, subject, relation, obj)
        if source != 'usuario_confirmado':
            raise ValueError('Esta interface aceita apenas informação confirmada pelo usuário')
        if not 0 <= confidence <= 1:
            raise ValueError('Confiança fora do intervalo')
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute('''SELECT id, object FROM relational_facts
                WHERE user_id=? AND subject=? AND relation=? AND valid_to IS NULL''',
                (user_id, subject, relation)).fetchall()
            old = {r['object'] for r in rows}
            if obj in old:
                db.rollback()
                return 'already_known'
            if relation in SINGLE and old:
                if expected_previous is None or old != set(expected_previous):
                    db.rollback()
                    return 'needs_confirmation'
                db.execute('''UPDATE relational_facts SET valid_to=?
                    WHERE user_id=? AND subject=? AND relation=? AND valid_to IS NULL''',
                    (now, user_id, subject, relation))
            db.execute('''INSERT INTO relational_facts
                (user_id,subject,relation,object,source,confidence,valid_from,valid_to,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                (user_id, subject, relation, obj, source, confidence, now, None, now))
            db.commit()
            return 'saved'

    def history(self, user_id, subject, relation):
        if relation not in ALLOWED:
            raise ValueError('Relação não cadastrada')
        with closing(self._connect()) as db:
            rows = db.execute('''SELECT * FROM relational_facts
                WHERE user_id=? AND subject=? AND relation=? ORDER BY id''',
                (user_id, subject, relation)).fetchall()
            return [dict(r) for r in rows]
