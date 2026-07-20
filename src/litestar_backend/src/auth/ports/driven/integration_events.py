from uuid import UUID

from shared.generics.integration_event import IntegrationEvent

USER_REGISTERED_STREAM = "user_registered"


class UserRegisteredIntegration(IntegrationEvent, frozen=True, kw_only=True):
    # Deliberately no email: PII stays out of the stream; consumers that need
    # profile data fetch it through an API with proper access control.
    event_type: str = "user_registered"
    user_id: UUID
    role: str
