"""Adapter for normalizing controlled webhook payloads."""

from fieldops.core.exceptions import ValidationError
from fieldops.intake.schemas import (
    InboundServiceRequest,
    InboundSource,
    WebhookPayload,
)


class WebhookInboundAdapter:
    """Normalizes generic controlled webhook payloads into InboundServiceRequest."""

    SUPPORTED_EVENT_TYPE = "service_request"

    @classmethod
    def normalize(cls, payload: WebhookPayload) -> InboundServiceRequest:
        if payload.event_type != cls.SUPPORTED_EVENT_TYPE:
            raise ValidationError(
                f"Unsupported webhook event_type '{payload.event_type}'. "
                f"Only '{cls.SUPPORTED_EVENT_TYPE}' is supported.",
                field="event_type",
            )

        customer = payload.customer
        return InboundServiceRequest(
            source=InboundSource.WEBHOOK,
            external_message_id=payload.event_id.strip(),
            customer_name=customer.name.strip(),
            customer_email=customer.email.strip() if customer.email else None,
            customer_phone=customer.phone.strip() if customer.phone else None,
            message=payload.message.strip(),
            metadata={
                "channel": "webhook",
                "original_event_id": payload.event_id.strip(),
                "event_type": payload.event_type,
            },
        )
