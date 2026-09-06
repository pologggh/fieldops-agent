"""Email integration subpackage."""

from fieldops.integrations.email.base import EmailClient, EmailSendResult
from fieldops.integrations.email.fake import FakeEmailClient
from fieldops.integrations.email.renderer import render_appointment_confirmation

__all__ = [
    "EmailClient",
    "EmailSendResult",
    "FakeEmailClient",
    "render_appointment_confirmation",
]
