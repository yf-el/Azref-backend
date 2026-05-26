"""AWS Lambda entry point — consumes Kafka records pushed by the
Confluent Cloud AWS Lambda Sink Connector, filters for
`user.onboarded.v1`, and upserts the user as a Salesforce Contact.

Idempotency is delegated to Salesforce via External ID upsert
(see SalesforceCrmClient). At-least-once delivery from Confluent is
safe: replaying the same event will hit the same SF Contact.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from crm.port import CrmClient
from kafka_events.schemas.user_events import UserEvent, UserOnboardedV1
from pydantic import TypeAdapter, ValidationError

from app.mapping import user_onboarded_to_contact

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_user_event_adapter = TypeAdapter(UserEvent)

# Singleton built lazily on the first invocation — survives across warm Lambda
# invocations so the Salesforce JWT exchange only runs on cold starts. Kept
# behind a getter so test modules can import this file without installing
# the Salesforce client library.
_default_client: CrmClient | None = None


def _get_default_client() -> CrmClient:
    global _default_client
    if _default_client is None:
        from crm.adapters.salesforce import SalesforceCrmClient

        _default_client = SalesforceCrmClient()
    return _default_client


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, int]:
    return asyncio.run(_process(event, _get_default_client()))


async def _process(event: dict[str, Any], client: CrmClient) -> dict[str, int]:
    records = _extract_records(event)
    counts = {"processed": 0, "skipped": 0, "failed": 0}

    for record in records:
        try:
            user_event = _parse_record(record)
        except (ValidationError, json.JSONDecodeError, ValueError):
            logger.exception("record_parse_failed", extra={"record": record})
            counts["failed"] += 1
            continue

        if not isinstance(user_event, UserOnboardedV1):
            # Other event_types on the same topic (signed_up, profile_updated)
            # are intentionally ignored in v1 — extend the dispatch table when
            # a second use-case comes in.
            counts["skipped"] += 1
            continue

        try:
            contact = user_onboarded_to_contact(user_event)
            await client.upsert_contact(contact)
            counts["processed"] += 1
        except Exception:
            # Permanent vs transient classification is deferred; v1 logs and
            # moves on so a single bad record doesn't block the batch. The
            # Kafka topic retains the offset — caller can replay if needed.
            logger.exception(
                "upsert_failed", extra={"event_id": str(user_event.event_id)}
            )
            counts["failed"] += 1

    logger.info("batch_processed", extra=counts)
    return counts


def _extract_records(event: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """Normalize the Confluent Sink Connector payload to a flat list.

    The managed AWS Lambda Sink Connector batches records; the exact shape
    varies slightly with the connector config, so we accept the common
    forms defensively rather than locking ourselves in.
    """
    if isinstance(event, list):
        return event
    if "records" in event and isinstance(event["records"], list):
        return event["records"]
    # Single-record invocation
    return [event]


def _parse_record(record: dict[str, Any]) -> UserEvent:
    value = record.get("value") or record.get("payload")
    if value is None:
        raise ValueError("record has no 'value' or 'payload' field")
    if isinstance(value, str):
        value = json.loads(value)
    return _user_event_adapter.validate_python(value)
