# -*- coding: utf-8 -*-
"""Memória persistente de episódios e fatos da EVA OS (SQLite)."""

import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.kernel.events import EventBus


class LongTermMemory:
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self._running = False
        default_path = "data/databases/eva_long_term.db"
        try:
            path = config.get("memory.long_term_db", default_path)
            if isinstance(path, dict):
                path = default_path
        except (AttributeError, TypeError):
            path = default_path
        self.db_path = str(path or default_path)
        self._init_db()
        self.logger.info("[LongTermMemory] Inicializado")

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        try:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute("""CREATE TABLE IF NOT EXISTS episodes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL, title TEXT,
                        content TEXT NOT NULL, importance REAL DEFAULT 0.5,
                        timestamp TEXT NOT NULL, metadata TEXT)""")
                    conn.execute("""CREATE TABLE IF NOT EXISTS facts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL, subject TEXT NOT NULL,
                        relation TEXT NOT NULL, object TEXT NOT NULL,
                        confidence REAL DEFAULT 0.7, source TEXT,
                        timestamp TEXT NOT NULL)""")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_eva_facts_user ON facts(user_id)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_eva_episodes_user ON episodes(user_id)")
        except Exception as exc:
            self.logger.error("[LongTermMemory] Erro ao inicializar banco: %s", exc)
            raise

    async def initialize(self) -> None:
        self._running = True
        self.logger.info("[LongTermMemory] Inicializado")

    async def store_episode(self, user_id: str, content: str,
                            importance: float = 0.5, metadata: Dict = None) -> int:
        try:
            title = content[:50] + "..." if len(content) > 50 else content
            with closing(self._connect()) as conn:
                with conn:
                    cursor = conn.execute("""INSERT INTO episodes
                        (user_id, title, content, importance, timestamp, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (user_id, title, content, importance, datetime.now().isoformat(),
                         json.dumps(metadata or {}, ensure_ascii=False)))
                    episode_id = cursor.lastrowid
            self.logger.info("[LongTermMemory] Episódio armazenado: %s", episode_id)
            return episode_id
        except Exception as exc:
            self.logger.error("[LongTermMemory] Erro ao armazenar episódio: %s", exc)
            return -1

    async def store_fact(self, user_id: str, subject: str, relation: str,
                         obj: str, confidence: float = 0.7,
                         source: str = None) -> int:
        try:
            with closing(self._connect()) as conn:
                with conn:
                    existing = conn.execute("""SELECT id FROM facts
                        WHERE user_id = ? AND subject = ? AND relation = ? AND object = ?
                        LIMIT 1""", (user_id, subject, relation, obj)).fetchone()
                    if existing:
                        return existing["id"]
                    cursor = conn.execute("""INSERT INTO facts
                        (user_id, subject, relation, object, confidence, source, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (user_id, subject, relation, obj, confidence, source,
                         datetime.now().isoformat()))
                    fact_id = cursor.lastrowid
            self.logger.info("[LongTermMemory] Fato armazenado: %s → %s → %s", subject, relation, obj)
            return fact_id
        except Exception as exc:
            self.logger.error("[LongTermMemory] Erro ao armazenar fato: %s", exc)
            return -1

    async def replace_explicit_name(self, user_id: str, subject: str,
                                    expected_values: List[str], new_value: str) -> bool:
        """Substitui nomes explicitamente ensinados em uma unica transacao.

        Nao altera fatos de outras fontes nem nomes de outros usuarios.
        Falha sem modificar nada se o estado anterior mudou.
        """
        if not user_id or not subject or not new_value or not expected_values:
            return False
        try:
            with closing(self._connect()) as conn:
                with conn:
                    rows = conn.execute(
                        """SELECT id, object FROM facts
                           WHERE user_id = ? AND subject = ? AND relation = 'nome'
                             AND source = 'ensinado_explicitamente'""",
                        (user_id, subject),
                    ).fetchall()
                    current = {row["object"] for row in rows}
                    if not rows or current != set(expected_values):
                        return False
                    # Remove somente registros desse nome explicitamente ensinado.
                    conn.execute(
                        """DELETE FROM facts WHERE user_id = ? AND subject = ?
                           AND relation = 'nome' AND source = 'ensinado_explicitamente'""",
                        (user_id, subject),
                    )
                    conn.execute(
                        """INSERT INTO facts
                           (user_id, subject, relation, object, confidence, source, timestamp)
                           VALUES (?, ?, 'nome', ?, 0.95, 'ensinado_explicitamente', ?)""",
                        (user_id, subject, new_value, datetime.now().isoformat()),
                    )
            self.logger.info("[LongTermMemory] Nome explicitamente ensinado corrigido: %s", subject)
            return True
        except Exception as exc:
            self.logger.error("[LongTermMemory] Erro ao corrigir nome: %s", exc)
            return False

    async def replace_explicit_fact(self, user_id: str, subject: str, relation: str,
                                    expected_values: List[str], new_value: str) -> bool:
        """Atualiza um fato geral apenas se o valor anterior ainda for o esperado."""
        if not all((user_id, subject, relation, expected_values, new_value)):
            return False
        try:
            with closing(self._connect()) as conn:
                with conn:
                    rows = conn.execute(
                        """SELECT object FROM facts WHERE user_id = ? AND subject = ?
                           AND relation = ? AND source = 'ensinado_geral_explicitamente'""",
                        (user_id, subject, relation)).fetchall()
                    if not rows or {row['object'] for row in rows} != set(expected_values):
                        return False
                    conn.execute(
                        """DELETE FROM facts WHERE user_id = ? AND subject = ?
                           AND relation = ? AND source = 'ensinado_geral_explicitamente'""",
                        (user_id, subject, relation))
                    conn.execute(
                        """INSERT INTO facts (user_id, subject, relation, object,
                           confidence, source, timestamp) VALUES
                           (?, ?, ?, ?, 0.95, 'ensinado_geral_explicitamente', ?)""",
                        (user_id, subject, relation, new_value, datetime.now().isoformat()))
            return True
        except Exception as exc:
            self.logger.error('[LongTermMemory] Erro ao corrigir fato geral: %s', exc)
            return False

    @staticmethod
    def _keywords(query: str, min_length: int) -> List[str]:
        return [word for word in re.findall(r"\w+", query or "", flags=re.UNICODE)
                if len(word) >= min_length]

    async def search_episodes(self, user_id: str, query: str,
                              limit: int = 5) -> List[Dict]:
        try:
            keywords = self._keywords(query, 4)
            sql = "SELECT id, content, importance, timestamp, metadata FROM episodes WHERE user_id = ?"
            params: List[Any] = [user_id]
            if keywords:
                sql += " AND (" + " OR ".join("content LIKE ?" for _ in keywords) + ")"
                params.extend("%" + kw + "%" for kw in keywords)
                sql += " ORDER BY importance DESC, timestamp DESC"
            else:
                sql += " ORDER BY timestamp DESC"
            sql += " LIMIT ?"
            params.append(max(0, int(limit)))
            with closing(self._connect()) as conn:
                rows = conn.execute(sql, params).fetchall()
            results = []
            for row in rows:
                item = dict(row)
                try:
                    item["metadata"] = json.loads(item["metadata"]) if item["metadata"] else {}
                except (ValueError, TypeError):
                    item["metadata"] = {}
                results.append(item)
            return results
        except Exception as exc:
            self.logger.error("[LongTermMemory] Erro na busca de episódios: %s", exc)
            return []

    async def search_facts(self, user_id: str, query: str,
                           limit: int = 5) -> List[Dict]:
        try:
            keywords = self._keywords(query, 3)
            sql = """SELECT id, subject, relation, object, confidence, source, timestamp
                     FROM facts WHERE user_id = ? AND relation != 'ultima_saudacao'"""
            params: List[Any] = [user_id]
            if keywords:
                sql += " AND (" + " OR ".join(
                    "(subject LIKE ? OR object LIKE ? OR relation LIKE ?)" for _ in keywords
                ) + ")"
                for kw in keywords:
                    params.extend(["%" + kw + "%"] * 3)
                sql += " ORDER BY confidence DESC, timestamp DESC"
            else:
                sql += " ORDER BY timestamp DESC"
            sql += " LIMIT ?"
            params.append(max(0, int(limit)))
            with closing(self._connect()) as conn:
                rows = conn.execute(sql, params).fetchall()
            results = [dict(row) for row in rows]
            self.logger.debug("[LongTermMemory] search_facts: %s resultados (user=%s)",
                              len(results), user_id)
            return results
        except Exception as exc:
            self.logger.error("[LongTermMemory] Erro na busca de fatos: %s", exc)
            return []

    async def get_last_greeting(self, user_id: str) -> Optional[str]:
        try:
            with closing(self._connect()) as conn:
                row = conn.execute("""SELECT object FROM facts
                    WHERE user_id = ? AND relation = 'ultima_saudacao'
                    ORDER BY timestamp DESC LIMIT 1""", (user_id,)).fetchone()
            return row["object"] if row else None
        except Exception as exc:
            self.logger.error("[LongTermMemory] Erro ao obter última saudação: %s", exc)
            return None

    async def update_last_greeting(self, user_id: str, date_str: str) -> bool:
        try:
            datetime.fromisoformat(date_str)
            with closing(self._connect()) as conn:
                with conn:
                    row = conn.execute("""SELECT id FROM facts
                        WHERE user_id = ? AND relation = 'ultima_saudacao'
                        ORDER BY timestamp DESC LIMIT 1""", (user_id,)).fetchone()
                    now = datetime.now().isoformat()
                    if row:
                        conn.execute("UPDATE facts SET object = ?, timestamp = ? WHERE id = ?",
                                     (date_str, now, row["id"]))
                    else:
                        conn.execute("""INSERT INTO facts
                            (user_id, subject, relation, object, confidence, source, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (user_id, "Usuario", "ultima_saudacao", date_str, 1.0,
                             "sistema", now))
            return True
        except Exception as exc:
            self.logger.error("[LongTermMemory] Erro ao atualizar última saudação: %s", exc)
            return False

    async def get_all_facts(self, user_id: str) -> List[Dict]:
        try:
            with closing(self._connect()) as conn:
                rows = conn.execute("""SELECT id, subject, relation, object, confidence,
                    source, timestamp FROM facts WHERE user_id = ?
                    ORDER BY timestamp DESC""", (user_id,)).fetchall()
            return [dict(row) for row in rows]
        except Exception as exc:
            self.logger.error("[LongTermMemory] Erro ao listar fatos: %s", exc)
            return []

    async def shutdown(self) -> None:
        self._running = False
        self.logger.info("[LongTermMemory] Desligado")
