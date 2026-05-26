"""Batch processing — the actual business logic, AWS-free.

Walks a list of Confluent records, keeps only `user.onboarded.v1` events,
maps each to a CrmContact, and dispatches to the CRM client. Returns
per-batch counters (processed / skipped / failed) for observability.

Pure async — no Lambda or AWS coupling. Drives the unit tests with a
fake CrmClient.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from crm.port import CrmClient
from kafka_events.schemas.user_events import UserOnboardedV1
from pydantic import ValidationError

from app.events import extract_records, parse_record
from app.mapping import user_onboarded_to_contact

logger = logging.getLogger()


async def process_batch(
    event: dict[str, Any] | list[Any], client: CrmClient
) -> dict[str, int]:
    """Process a batch of Confluent Sink Connector records.

    Returns counts {"processed", "skipped", "failed"}. A single bad record
    never blocks the batch — we log + count + continue, and the Kafka
    offset stays uncommitted only if the whole invocation raises.
    """
    records = extract_records(event)
    counts = {"processed": 0, "skipped": 0, "failed": 0}

    for record in records:
        try:
            user_event = parse_record(record)
        except (ValidationError, json.JSONDecodeError, ValueError):
            logger.exception("record_parse_failed", extra={"record": record})
            counts["failed"] += 1
            continue

        # if not isinstance(user_event, UserOnboardedV1):
        #     # Other event types on the same topic (signed_up,
        #     # profile_updated) are intentionally ignored in v1.
        #     counts["skipped"] += 1
        #     continue

        try:
            contact = user_onboarded_to_contact(user_event)
            await client.upsert_contact(contact)
            counts["processed"] += 1
        except Exception:
            logger.exception(
                "upsert_failed", extra={"event_id": str(user_event.event_id)}
            )
            counts["failed"] += 1

    logger.info("batch_processed", extra=counts)
    return counts
