import asyncio
import logging
from typing import Any

from simple_salesforce import Salesforce
from simple_salesforce.exceptions import SalesforceError

from crm.config import CrmConfig
from crm.models import CrmContact

logger = logging.getLogger(__name__)


class SalesforceCrmClient:
    """CrmClient implementation backed by Salesforce.

    Auth uses OAuth 2.0 JWT Bearer Flow via `simple-salesforce`: no
    password is ever held by the Lambda — only the RSA private key
    (loaded from Secrets Manager). The client is built lazily on first
    `upsert_contact` call and reused across invocations as long as the
    Lambda container stays warm. SF access tokens last ~2h, so warm
    re-use is the common case.

    Idempotency: `CrmContact.external_id` maps to a Salesforce External
    ID custom field (default `External_User_Id__c`). SF's upsert is
    atomic — replaying the same event never creates a duplicate.
    """

    def __init__(self, config: CrmConfig | None = None) -> None:
        self._explicit_config = config
        self._sf: Salesforce | None = None
        self._init_lock = asyncio.Lock()

    @property
    def _config(self) -> CrmConfig:
        if self._explicit_config is None:
            self._explicit_config = CrmConfig()
        return self._explicit_config

    async def _ensure_started(self) -> Salesforce:
        if self._sf is not None:
            return self._sf
        async with self._init_lock:
            if self._sf is not None:
                return self._sf
            sf = await asyncio.to_thread(self._build_client)
            self._sf = sf
            logger.info(
                "salesforce_client_started",
                extra={
                    "username": self._config.username,
                    "domain": self._config.domain,
                },
            )
            return sf

    def _build_client(self) -> Salesforce:
        # simple-salesforce performs the JWT Bearer flow internally when
        # given a private key + consumer_key + username — it builds the
        # JWT, POSTs it to the token endpoint, and stores the access
        # token + instance URL on the returned client.
        return Salesforce(
            username=self._config.username,
            consumer_key=self._config.consumer_key,
            privatekey=self._config.private_key,
            domain=self._config.domain,
        )

    async def upsert_contact(self, contact: CrmContact) -> None:
        sf = await self._ensure_started()
        payload = self._to_sf_payload(contact)
        external_id_ref = (
            f"{self._config.external_id_field}/{contact.external_id}"
        )
        try:
            await asyncio.to_thread(sf.Contact.upsert, external_id_ref, payload)
        except SalesforceError:
            logger.exception(
                "salesforce_upsert_failed",
                extra={
                    "external_id": contact.external_id,
                    "external_id_field": self._config.external_id_field,
                },
            )
            raise

    @staticmethod
    def _to_sf_payload(contact: CrmContact) -> dict[str, Any]:
        # LastName is mandatory on Salesforce Contact. The events we
        # consume today (UserOnboardedV1) don't carry a name, so we
        # fall back through email then external_id — the upsert must
        # never fail just because the user signed up without a name.
        last_name = (
            contact.last_name or contact.email or contact.external_id
        )
        return {
            "Email": contact.email,
            "FirstName": contact.first_name,
            "LastName": last_name,
            "Title": contact.profession,
            "Description": contact.usage_type,
        }
