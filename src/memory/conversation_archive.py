
"""Persistent conversation archive for EVA OS."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


class ConversationArchive:
    def __init__(self, db_path):
        self.db_path = Path(db_path)

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path), timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with closing(self._connect()) as conn:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT NOT NULL UNIQUE,
                        user_id TEXT NOT NULL,
                        session_id TEXT,
                        role TEXT NOT NULL
                            CHECK(role IN ('user', 'assistant')),
                        content TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        source TEXT,
                        metadata TEXT
                    )
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS
                    idx_conversation_messages_user
                    ON conversation_messages(user_id, id)
                """)

    def store_message(
        self,
        event_id,
        user_id,
        role,
        content,
        session_id=None,
        source=None,
        metadata=None,
        timestamp=None,
    ):
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id is required")

        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id is required")

        if role not in ("user", "assistant"):
            raise ValueError("invalid role")

        if not isinstance(content, str) or not content.strip():
            raise ValueError("content is required")

        timestamp = timestamp or datetime.now().isoformat()
        metadata_json = json.dumps(
            metadata or {}, ensure_ascii=False
        )

        with closing(self._connect()) as conn:
            with conn:
                conn.execute("BEGIN IMMEDIATE")

                existing = conn.execute("""
                    SELECT user_id, session_id, role, content,
                           timestamp, source, metadata
                    FROM conversation_messages
                    WHERE event_id = ?
                """, (event_id,)).fetchone()

                incoming = (
                    user_id,
                    session_id,
                    role,
                    content,
                    timestamp,
                    source,
                    metadata_json,
                )

                if existing is not None:
                    stored = tuple(existing)

                    if stored == incoming:
                        return False

                    raise ValueError(
                        "event_id conflict: existing event differs"
                    )

                try:
                    conn.execute("""
                        INSERT INTO conversation_messages
                        (event_id, user_id, session_id, role,
                         content, timestamp, source, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (event_id,) + incoming)
                except sqlite3.IntegrityError:
                    raise ValueError(
                        "event_id conflict or database constraint"
                    ) from None

                return True

    def get_history(self, user_id, limit=50):
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id is required")

        limit = max(0, int(limit))

        if limit == 0:
            return []

        with closing(self._connect()) as conn:
            rows = conn.execute("""
                SELECT id, event_id, user_id, session_id,
                       role, content, timestamp, source, metadata
                FROM conversation_messages
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (user_id, limit)).fetchall()

        return [dict(row) for row in reversed(rows)]

    def count_messages(self, user_id=None):
        with closing(self._connect()) as conn:
            if user_id is None:
                row = conn.execute(
                    "SELECT COUNT(*) FROM conversation_messages"
                ).fetchone()
            else:
                row = conn.execute("""
                    SELECT COUNT(*) FROM conversation_messages
                    WHERE user_id = ?
                """, (user_id,)).fetchone()

        return row[0]
