"""Conversation turn identity helpers for EVA OS."""

from uuid import UUID


def validate_turn_id(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("turn_id must be a nonempty string")

    try:
        parsed = UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError("turn_id must be a valid UUID") from exc

    if str(parsed) != value.lower():
        raise ValueError("turn_id must use canonical UUID format")

    return str(parsed)


def resolve_turn_id(event):
    data = getattr(event, "data", None)

    if not isinstance(data, dict):
        raise ValueError("event data must be a dictionary")

    supplied = data.get("turn_id")

    if supplied is not None:
        return validate_turn_id(supplied)

    event_id = getattr(event, "id", None)

    if event_id is None:
        raise ValueError("event has no usable identifier")

    return validate_turn_id(event_id)
