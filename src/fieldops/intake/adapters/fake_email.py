"""Adapter for normalizing simulated/fake email payloads."""

from fieldops.intake.schemas import (
    FakeEmailPayload,
    InboundServiceRequest,
    InboundSource,
)


class FakeEmailInboundAdapter:
    """Normalizes simulated incoming email into InboundServiceRequest."""

    @staticmethod
    def normalize(payload: FakeEmailPayload) -> InboundServiceRequest:
        subject = (payload.subject or "").strip()
        body = (payload.body or "").strip()

        if subject and body:
            combined_message = f"{subject}\n\n{body}"
        elif subject:
            combined_message = subject
        else:
            combined_message = body

        return InboundServiceRequest(
            source=InboundSource.FAKE_EMAIL,
            external_message_id=payload.message_id.strip(),
            customer_name=payload.from_name.strip(),
            customer_email=payload.from_email.strip() if payload.from_email else None,
            customer_phone=None,
            message=combined_message,
            metadata={
                "channel": "fake_email",
                "original_message_id": payload.message_id.strip(),
                "subject": subject,
            },
        )
