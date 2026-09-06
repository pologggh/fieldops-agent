"""Unified Inbound Request Intake Layer for FieldOps Agent."""

from fieldops.intake.adapters import (
    FakeEmailInboundAdapter,
    WebInboundAdapter,
    WebhookInboundAdapter,
)
from fieldops.intake.schemas import (
    FakeEmailPayload,
    InboundResponse,
    InboundServiceRequest,
    InboundSource,
    WebhookCustomerPayload,
    WebhookPayload,
)
from fieldops.intake.service import InboundRequestService

__all__ = [
    "InboundSource",
    "InboundServiceRequest",
    "InboundResponse",
    "FakeEmailPayload",
    "WebhookCustomerPayload",
    "WebhookPayload",
    "InboundRequestService",
    "WebInboundAdapter",
    "FakeEmailInboundAdapter",
    "WebhookInboundAdapter",
]
