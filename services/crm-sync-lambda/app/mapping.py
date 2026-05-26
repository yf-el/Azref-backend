from crm.models import CrmContact
from kafka_events.schemas.user_events import UserOnboardedV1


def user_onboarded_to_contact(event: UserOnboardedV1) -> CrmContact:
    """Project a `user.onboarded.v1` event onto the vendor-neutral
    `CrmContact` model. The adapter handles vendor-specific quirks
    (e.g. Salesforce LastName fallback) downstream — this function
    stays pure and trivially testable.
    """
    return CrmContact(
        external_id=event.user_id,
        email=event.payload.user_email,
        profession=event.payload.profession,
        usage_type=event.payload.usage_type,
    )
