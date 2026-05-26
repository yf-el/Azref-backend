from kafka_events.schemas.user_events import UserOnboardedPayload, UserOnboardedV1

from app.mapping import user_onboarded_to_contact


def test_user_onboarded_to_contact_carries_business_fields():
    event = UserOnboardedV1(
        user_id="usr_123",
        payload=UserOnboardedPayload(
            user_email="a@b.com",
            profession="Avocat",
            usage_type="professional",
        ),
    )

    contact = user_onboarded_to_contact(event)

    assert contact.external_id == "usr_123"
    assert contact.email == "a@b.com"
    assert contact.profession == "Avocat"
    assert contact.usage_type == "professional"
    # No name in the event payload — adapter handles the SF LastName fallback.
    assert contact.first_name is None
    assert contact.last_name is None


def test_user_onboarded_to_contact_handles_missing_email():
    event = UserOnboardedV1(
        user_id="usr_456",
        payload=UserOnboardedPayload(
            user_email=None,
            profession="Etudiant",
            usage_type="personal",
        ),
    )

    contact = user_onboarded_to_contact(event)

    assert contact.external_id == "usr_456"
    assert contact.email is None
