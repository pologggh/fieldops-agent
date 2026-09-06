"""Adapter for normalizing Web API / Form requests."""

from fieldops.intake.schemas import InboundServiceRequest, InboundSource
from fieldops.llm.schemas import ServiceRequestCreateInput


class WebInboundAdapter:
    """Normalizes Web Form submissions into InboundServiceRequest."""

    @staticmethod
    def normalize(payload: ServiceRequestCreateInput) -> InboundServiceRequest:
        return InboundServiceRequest(
            source=InboundSource.WEB,
            external_message_id=None,
            customer_name=payload.customer_name.strip(),
            customer_email=str(payload.email).strip() if payload.email else None,
            customer_phone=payload.phone.strip() if payload.phone else None,
            message=payload.message.strip(),
            metadata={"channel": "web_form"},
        )
