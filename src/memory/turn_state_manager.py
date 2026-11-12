"""Persistent lifecycle tracking for EVA OS conversation turns."""

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


class TurnStateManager:
    STATES = ("received", "processing", "completed", "failed")

    TRANSITIONS = {
        "received": {"processing", "failed"},
        "processing": {"completed", "failed"},
        "failed": {"processing"},
        "completed": set(),
    }

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
                    CREATE TABLE IF NOT EXISTS conversation_turn_states (
                        turn_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        state TEXT NOT NULL CHECK (
                            state IN (
                                'received',
                                'processing',
                                'completed',
                                'failed'
                            )
                        ),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS
                    idx_conversation_turn_states_state
                    ON conversation_turn_states(state)
                """)

    def register_turn(self, turn_id, user_id):
        if not isinstance(turn_id, str) or not turn_id.strip():
            raise ValueError("turn_id is required")

        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id is required")

        now = datetime.now().isoformat()

        with closing(self._connect()) as conn:
            with conn:
                conn.execute("BEGIN IMMEDIATE")

                existing = conn.execute("""
                    SELECT user_id
                    FROM conversation_turn_states
                    WHERE turn_id = ?
                """, (turn_id,)).fetchone()

                if existing is not None:
                    if existing["user_id"] != user_id:
                        raise ValueError("turn_id belongs to another user")
                    return False

                conn.execute("""
                    INSERT INTO conversation_turn_states
                    (turn_id, user_id, state, created_at, updated_at)
                    VALUES (?, ?, 'received', ?, ?)
                """, (turn_id, user_id, now, now))

                return True

    def change_state(self, turn_id, expected, new_state):
        if new_state not in self.TRANSITIONS.get(expected, set()):
            raise ValueError("invalid state transition")

        now = datetime.now().isoformat()

        with closing(self._connect()) as conn:
            with conn:
                result = conn.execute("""
                    UPDATE conversation_turn_states
                    SET state = ?, updated_at = ?
                    WHERE turn_id = ? AND state = ?
                """, (new_state, now, turn_id, expected))

                if result.rowcount != 1:
                    raise ValueError("unexpected current state")

        return True

    def get_turn(self, turn_id):
        with closing(self._connect()) as conn:
            row = conn.execute("""
                SELECT turn_id, user_id, state,
                       created_at, updated_at
                FROM conversation_turn_states
                WHERE turn_id = ?
            """, (turn_id,)).fetchone()

            return dict(row) if row is not None else None

    def get_pending(self, user_id=None):
        query = """
            SELECT turn_id, user_id, state,
                   created_at, updated_at
            FROM conversation_turn_states
            WHERE state IN ('received', 'processing', 'failed')
        """

        params = []

        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)

        query += " ORDER BY created_at, turn_id"

        with closing(self._connect()) as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
