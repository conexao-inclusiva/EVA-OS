"""Atomic conversation persistence coordinator for EVA OS."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from src.memory.conversation_archive import ConversationArchive
from src.memory.turn_state_manager import TurnStateManager


class ConversationCoordinator:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.archive = ConversationArchive(self.db_path)
        self.states = TurnStateManager(self.db_path)

    def initialize(self):
        self.archive.initialize()
        self.states.initialize()

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path), timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _required(value, name):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(name + " is required")
        return value

    def receive_turn(
        self, turn_id, user_id, content,
        session_id=None, source=None, timestamp=None,
        metadata=None
    ):
        self._required(turn_id, "turn_id")
        self._required(user_id, "user_id")
        self._required(content, "content")

        timestamp = timestamp or datetime.now().isoformat()
        metadata_json = json.dumps(
            metadata if metadata is not None else {"turn_id": turn_id},
            ensure_ascii=False
        )
        event_id = turn_id + ":user"

        with closing(self._connect()) as conn:
            with conn:
                conn.execute("BEGIN IMMEDIATE")

                existing = conn.execute("""
                    SELECT m.user_id, m.session_id, m.role,
                           m.content, m.timestamp, m.source,
                           m.metadata, t.state, t.user_id AS turn_user
                    FROM conversation_messages AS m
                    LEFT JOIN conversation_turn_states AS t
                      ON t.turn_id = ?
                    WHERE m.event_id = ?
                """, (turn_id, event_id)).fetchone()

                if existing is not None:
                    incoming = (
                        user_id, session_id, "user", content,
                        timestamp, source, metadata_json
                    )
                    stored = tuple(existing[key] for key in (
                        "user_id", "session_id", "role", "content",
                        "timestamp", "source", "metadata"
                    ))
                    if stored != incoming:
                        raise ValueError("conflicting user event")
                    if existing["state"] is None:
                        raise ValueError("turn state missing")
                    if existing["turn_user"] != user_id:
                        raise ValueError("turn identity conflict")
                    return False

                state = conn.execute("""
                    SELECT user_id FROM conversation_turn_states
                    WHERE turn_id = ?
                """, (turn_id,)).fetchone()

                if state is not None:
                    raise ValueError("turn exists without user message")

                now = datetime.now().isoformat()

                conn.execute("""
                    INSERT INTO conversation_turn_states
                    (turn_id, user_id, state, created_at, updated_at)
                    VALUES (?, ?, 'received', ?, ?)
                """, (turn_id, user_id, now, now))

                conn.execute("""
                    INSERT INTO conversation_messages
                    (event_id, user_id, session_id, role,
                     content, timestamp, source, metadata)
                    VALUES (?, ?, ?, 'user', ?, ?, ?, ?)
                """, (
                    event_id, user_id, session_id, content,
                    timestamp, source, metadata_json
                ))

                return True

    def start_turn(self, turn_id):
        return self.states.change_state(
            turn_id, "received", "processing"
        )

    def complete_turn(
        self, turn_id, response,
        timestamp=None, source="brain",
        metadata=None
    ):
        self._required(turn_id, "turn_id")
        self._required(response, "response")

        timestamp = timestamp or datetime.now().isoformat()
        metadata_json = json.dumps(
            metadata if metadata is not None else {"turn_id": turn_id},
            ensure_ascii=False
        )

        with closing(self._connect()) as conn:
            with conn:
                conn.execute("BEGIN IMMEDIATE")

                state = conn.execute("""
                    SELECT user_id, state
                    FROM conversation_turn_states
                    WHERE turn_id = ?
                """, (turn_id,)).fetchone()

                if state is None:
                    raise ValueError("turn does not exist")

                if state["state"] == "completed":
                    existing = conn.execute("""
                        SELECT user_id, role, content, timestamp,
                               source, metadata
                        FROM conversation_messages
                        WHERE event_id = ?
                    """, (turn_id + ":assistant",)).fetchone()

                    if existing is None:
                        raise ValueError("completed turn missing response")

                    expected = (
                        state["user_id"],
                        "assistant",
                        response,
                        timestamp,
                        source,
                        metadata_json,
                    )

                    actual = tuple(existing[key] for key in (
                        "user_id", "role", "content", "timestamp",
                        "source", "metadata"
                    ))

                    if actual != expected:
                        raise ValueError("conflicting assistant event")

                    return False

                if state["state"] != "processing":
                    raise ValueError("turn is not processing")

                user_event = conn.execute("""
                    SELECT user_id, session_id
                    FROM conversation_messages
                    WHERE event_id = ? AND role = 'user'
                """, (turn_id + ":user",)).fetchone()

                if user_event is None:
                    raise ValueError("user message missing")

                if user_event["user_id"] != state["user_id"]:
                    raise ValueError("turn identity conflict")

                conn.execute("""
                    INSERT INTO conversation_messages
                    (event_id, user_id, session_id, role,
                     content, timestamp, source, metadata)
                    VALUES (?, ?, ?, 'assistant', ?, ?, ?, ?)
                """, (
                    turn_id + ":assistant",
                    state["user_id"],
                    user_event["session_id"],
                    response, timestamp, source, metadata_json
                ))

                result = conn.execute("""
                    UPDATE conversation_turn_states
                    SET state = 'completed', updated_at = ?
                    WHERE turn_id = ? AND state = 'processing'
                """, (timestamp, turn_id))

                if result.rowcount != 1:
                    raise ValueError("state transition failed")

                return True

    def get_turn(self, turn_id):
        return self.states.get_turn(turn_id)

    def get_pending(self, user_id=None):
        return self.states.get_pending(user_id)
