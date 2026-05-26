import asyncio
import json
from uuid import uuid4

import pytest

from app.processing import process_batch
from crm.models import CrmContact


class FakeCrmClient:
    def __init__(self) -> None:
        self.upserts: list[CrmContact] = []
        self.fail_next = False

    async def upsert_contact(self, contact: CrmContact) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("simulated SF outage")
        self.upserts.append(contact)


def _onboarded_record(user_id: str = "usr_1", email: str = "a@b.com") -> dict:
    payload = {
        "event_id": str(uuid4()),
        "event_type": "user.onboarded.v1",
        "occurred_at": "2026-05-25T10:00:00Z",
        "user_id": user_id,
        "payload": {
            "user_email": email,
            "profession": "Avocat",
            "usage_type": "professional",
        },
    }
    return {"value": json.dumps(payload), "topic": "azref.user.events"}


def _signed_up_record() -> dict:
    payload = {
        "event_id": str(uuid4()),
        "event_type": "user.signed_up.v1",
        "occurred_at": "2026-05-25T10:00:00Z",
        "user_id": "usr_other",
        "payload": {"user_email": "x@y.com", "attribution": None},
    }
    return {"value": json.dumps(payload), "topic": "azref.user.events"}


def test_processes_onboarded_event():
    client = FakeCrmClient()
    event = [_onboarded_record(user_id="usr_42", email="z@z.com")]

    result = asyncio.run(process_batch(event, client))

    assert result == {"processed": 1, "skipped": 0, "failed": 0}
    assert len(client.upserts) == 1
    assert client.upserts[0].external_id == "usr_42"
    assert client.upserts[0].email == "z@z.com"


def test_filters_non_onboarded_events():
    client = FakeCrmClient()
    event = [_signed_up_record(), _onboarded_record()]

    result = asyncio.run(process_batch(event, client))

    assert result == {"processed": 1, "skipped": 1, "failed": 0}
    assert len(client.upserts) == 1


def test_handles_malformed_record():
    client = FakeCrmClient()
    event = [{"value": "not-json", "topic": "azref.user.events"}]

    result = asyncio.run(process_batch(event, client))

    assert result == {"processed": 0, "skipped": 0, "failed": 1}
    assert client.upserts == []


def test_failed_upsert_does_not_block_batch():
    client = FakeCrmClient()
    client.fail_next = True
    event = [_onboarded_record(user_id="usr_a"), _onboarded_record(user_id="usr_b")]

    result = asyncio.run(process_batch(event, client))

    assert result == {"processed": 1, "skipped": 0, "failed": 1}
    assert len(client.upserts) == 1
    assert client.upserts[0].external_id == "usr_b"


def test_accepts_records_field_envelope():
    client = FakeCrmClient()
    event = {"records": [_onboarded_record()]}

    result = asyncio.run(process_batch(event, client))

    assert result == {"processed": 1, "skipped": 0, "failed": 0}
