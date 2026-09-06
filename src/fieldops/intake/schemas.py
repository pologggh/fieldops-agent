"""Pydantic schemas and contracts for the Inbound Request Intake Layer."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class InboundSource(str, Enum):
    """Supported request intake sources."""

    WEB = "web"
    FAKE_EMAIL = "fake_email"
    WEBHOOK = "webhook"
    CUSTOMER_PORTAL = "customer_portal"
    CUSTOMER_CONVERSATION = "customer_conversation"



class InboundServiceRequest(BaseModel):
    """Normalized internal representation of a service request across all channels."""

    source: InboundSource
    external_message_id: str | None = None
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    message: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class InboundResponse(BaseModel):
    """Unified API response for inbound request intake across channels."""

    request_id: str
    service_request_id: int | None = None
    workflow_status: str
    source: str
    duplicate: bool = False
    details: dict[str, Any] | None = None


# ==============================================================================
# Channel-specific Raw Payloads
# ==============================================================================


class FakeEmailPayload(BaseModel):
    """Inbound email payload structure for simulated email intake."""

    message_id: str
    from_name: str
    from_email: str
    subject: str = ""
    body: str


class WebhookCustomerPayload(BaseModel):
    """Customer information embedded in webhook payload."""

    name: str
    email: str | None = None
    phone: str | None = None


class WebhookPayload(BaseModel):
    """Generic controlled webhook payload structure."""

    event_id: str
    event_type: str
    customer: WebhookCustomerPayload
    message: str
