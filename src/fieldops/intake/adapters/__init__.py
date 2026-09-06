"""Adapters for normalizing incoming requests across channels."""

from fieldops.intake.adapters.fake_email import FakeEmailInboundAdapter
from fieldops.intake.adapters.web import WebInboundAdapter
from fieldops.intake.adapters.webhook import WebhookInboundAdapter

__all__ = [
    "WebInboundAdapter",
    "FakeEmailInboundAdapter",
    "WebhookInboundAdapter",
]
