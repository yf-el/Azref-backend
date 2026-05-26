from pydantic import BaseModel, ConfigDict


class CrmContact(BaseModel):
    """Vendor-neutral CRM contact.

    No Salesforce-specific fields leak here — `external_id` is the stable
    business key (the platform user_id), used by adapters to upsert against
    whatever native external-id mechanism the target CRM exposes.
    """

    model_config = ConfigDict(extra="forbid")

    external_id: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    profession: str | None = None
    usage_type: str | None = None
