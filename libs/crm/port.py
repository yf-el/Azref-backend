from typing import Protocol

from crm.models import CrmContact


class CrmClient(Protocol):
    """Vendor-agnostic CRM contract.

    V1 exposes only `upsert_contact` — the single operation our first
    consumer needs. Other CRUD (delete, find, update by query) will be
    added when a second concrete use-case requires them, not before.
    """

    async def upsert_contact(self, contact: CrmContact) -> None:
        """Create or update a contact, keyed on `contact.external_id`.

        Implementations MUST be idempotent: replaying the same event with
        the same `external_id` must not create a duplicate record. The
        common pattern is to map `external_id` to the CRM's native
        external-id mechanism (Salesforce External ID, HubSpot custom
        unique property, ...).
        """
        ...
