"""Fake in-memory email client for development and automated testing."""

import hashlib
import logging
from typing import Any

from fieldops.integrations.email.base import EmailClient, EmailSendResult
from fieldops.integrations.exceptions import (
    PermanentIntegrationError,
    TransientIntegrationError,
)

logger = logging.getLogger(__name__)


class FakeEmailClient(EmailClient):
    """Simulated email provider with deterministic IDs and fault injection hooks."""

    def __init__(self) -> None:
        self.sent_emails: list[dict[str, Any]] = []
        self._transient_failure_countdown: int = 0
        self._permanent_failure_active: bool = False
        self._failure_message: str = ""
        self.call_count: int = 0

    def simulate_transient_failure(
        self, count: int = 1, message: str = "Simulated temporary SMTP/API outage (429/503)"
    ) -> None:
        """Inject transient failures that fail count times before succeeding."""
        self._transient_failure_countdown = count
        self._failure_message = message

    def simulate_permanent_failure(
        self, message: str = "Simulated permanent email delivery rejection (550 User unknown)"
    ) -> None:
        """Inject permanent non-retryable failure."""
        self._permanent_failure_active = True
        self._failure_message = message

    def reset_simulation(self) -> None:
        """Clear all simulated failure conditions."""
        self._transient_failure_countdown = 0
        self._permanent_failure_active = False
        self._failure_message = ""

    def clear(self) -> None:
        """Clear sent emails and simulation states."""
        self.sent_emails.clear()
        self.reset_simulation()
        self.call_count = 0

    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> EmailSendResult:
        """Simulate sending an email."""
        self.call_count += 1

        if not recipient or "@" not in recipient:
            raise PermanentIntegrationError(
                f"Invalid recipient email address: '{recipient}'",
                provider="fake_email",
            )

        if self._permanent_failure_active:
            logger.warning("FakeEmailClient: Raising simulated permanent failure")
            raise PermanentIntegrationError(
                self._failure_message or "Simulated permanent email delivery error",
                provider="fake_email",
            )

        if self._transient_failure_countdown > 0:
            self._transient_failure_countdown -= 1
            logger.warning(
                "FakeEmailClient: Raising simulated transient failure (remaining: %d)",
                self._transient_failure_countdown,
            )
            raise TransientIntegrationError(
                self._failure_message or "Simulated transient email connection timeout",
                provider="fake_email",
            )

        # Deterministic message ID
        meta = metadata or {}
        if "notification_job_id" in meta:
            message_id = f"fake-msg-job-{meta['notification_job_id']}"
        elif "appointment_id" in meta:
            message_id = f"fake-msg-appt-{meta['appointment_id']}"
        else:
            digest = hashlib.sha256(f"{recipient}:{subject}".encode()).hexdigest()[:12]
            message_id = f"fake-msg-{digest}"

        record = {
            "message_id": message_id,
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "metadata": meta,
        }
        self.sent_emails.append(record)
        logger.info("FakeEmailClient: Sent simulated email to %s (id=%s)", recipient, message_id)

        return EmailSendResult(
            provider_message_id=message_id,
            status="sent",
            provider="fake_email",
        )
