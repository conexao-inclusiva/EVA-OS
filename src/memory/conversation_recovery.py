"""Read-only recovery inspection for interrupted conversations."""

from contextlib import closing

from src.memory.conversation_coordinator import ConversationCoordinator


class ConversationRecovery:
    def __init__(self, db_path):
        self.coordinator = ConversationCoordinator(db_path)

    def inspect_pending(self):
        pending = self.coordinator.get_pending()
        results = []

        with closing(self.coordinator._connect()) as conn:
            for turn in pending:
                turn_id = turn["turn_id"]

                message = conn.execute("""
                    SELECT event_id, user_id, session_id,
                           content, timestamp, source
                    FROM conversation_messages
                    WHERE event_id = ? AND role = 'user'
                """, (turn_id + ":user",)).fetchone()

                response = conn.execute("""
                    SELECT event_id
                    FROM conversation_messages
                    WHERE event_id = ? AND role = 'assistant'
                """, (turn_id + ":assistant",)).fetchone()

                results.append({
                    "turn_id": turn_id,
                    "user_id": turn["user_id"],
                    "state": turn["state"],
                    "message": dict(message) if message else None,
                    "has_response": response is not None,
                    "requires_review": True,
                })

        return results
