"""Confluent Sink Connector record handling — knows the wire format.

The connector may send a single dict, a list of records, or a
`{"records": [...]}` envelope depending on its config and version. Each
record may also be wrapped under a `payload` field (Confluent's default
Lambda envelope), with the actual message value base64-encoded when the
connector is configured with input format `BYTES`. This module isolates
all that wire-format knowledge so the rest of the code only deals with
strongly-typed `UserEvent` objects.
"""
from __future__ import annotations

import base64
import binascii
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
    """Parse one record into a typed UserEvent.

    Handles two wrapping conventions: the Confluent Lambda Sink wraps each
    Kafka record under a `payload` field; some test fixtures pass the
    record flat. The value itself may be base64-encoded raw bytes (input
    format `BYTES`) or a plain JSON string (tests).

    Raises `ValueError` if the record carries no value, `json.JSONDecodeError`
    if the value isn't valid JSON, or `pydantic.ValidationError` if the
    payload doesn't match any known UserEvent shape.
    """
    # Confluent wraps {topic, partition, key, value, ...} under "payload".
    if isinstance(record.get("payload"), dict):
        record = record["payload"]

    value = record.get("value")
    if value is None:
        raise ValueError("record has no 'value' field")

    if isinstance(value, str):
        # With input format BYTES, value is base64-encoded raw Kafka bytes.
        # Tests pass a plain JSON string — fall back to direct json.loads.
        try:
            decoded = base64.b64decode(value, validate=True)
            value = json.loads(decoded)
        except (binascii.Error, ValueError):
            value = json.loads(value)

    return _user_event_adapter.validate_python(value)
