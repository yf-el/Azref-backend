"""Confluent Sink Connector record handling — knows the wire format.

The connector may send a single dict, a list of records, or a
`{"records": [...]}` envelope depending on its config and version. This
module isolates that knowledge so the rest of the code only deals with
strongly-typed `UserEvent` objects.
"""
from __future__ import annotations

import json
from typing import Any

from kafka_events.schemas.user_events import UserEvent
from pydantic import TypeAdapter

_user_event_adapter = TypeAdapter(UserEvent)


def extract_records(event: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """Normalize the Sink Connector payload to a flat list of records."""
    if isinstance(event, list):
        return event
    if isinstance(event, dict) and isinstance(event.get("records"), list):
        return event["records"]
    # Single-record invocation — wrap into a list for uniform handling.
    return [event]


def parse_record(record: dict[str, Any]) -> UserEvent:
    """Parse one record's `value`/`payload` field into a typed UserEvent.

    Raises `ValueError` if the record carries no value, `json.JSONDecodeError`
    if the value isn't valid JSON, or `pydantic.ValidationError` if the
    payload doesn't match any known UserEvent shape.
    """
    value = record.get("value") or record.get("payload")
    if value is None:
        raise ValueError("record has no 'value' or 'payload' field")
    if isinstance(value, str):
        value = json.loads(value)
    return _user_event_adapter.validate_python(value)
