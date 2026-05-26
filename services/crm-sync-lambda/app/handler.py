"""AWS Lambda entry point.

Invoked by the Confluent AWS Lambda Sink Connector when it has Kafka
records to deliver. Kept intentionally thin: lifecycle glue only
(build the CRM client once per warm container, delegate to processing).

➜ Read next: `processing.py` for the actual work,
              `events.py` for the Confluent record format.
"""
from __future__ import annotations

import asyncio
from typing import Any

from crm.port import CrmClient

from app.processing import process_batch

# Built lazily on the first invocation and kept across warm container
# reuses — the Salesforce JWT exchange only runs on cold starts.
_default_client: CrmClient | None = None


def _get_default_client() -> CrmClient:
    global _default_client
    if _default_client is None:
        # Lazy import keeps the module importable by tests without the
        # `simple-salesforce` dependency installed.
        from crm.adapters.salesforce import SalesforceCrmClient

        _default_client = SalesforceCrmClient()
    return _default_client


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, int]:
    """AWS Lambda entry point. See module docstring."""
    return asyncio.run(process_batch(event, _get_default_client()))
