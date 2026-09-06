"""External integration clients and factory providers."""

from fieldops.core.config import settings
from fieldops.integrations.calendar.base import (
    CalendarClient,
    CalendarEventCreate,
    CalendarEventResult,
)
from fieldops.integrations.calendar.fake import FakeCalendarClient
from fieldops.integrations.calendar.google import GoogleCalendarClient
from fieldops.integrations.calendar.reconciliation import CalendarReconciliationService
from fieldops.integrations.email.base import EmailClient, EmailSendResult
from fieldops.integrations.email.fake import FakeEmailClient
from fieldops.integrations.exceptions import (
    AuthenticationIntegrationError,
    IntegrationError,
    PermanentIntegrationError,
    TransientIntegrationError,
)

_calendar_client_instance: CalendarClient | None = None
_email_client_instance: EmailClient | None = None


def get_calendar_client() -> CalendarClient:
    """Return configured calendar client based on settings, enforcing production safeguards."""
    global _calendar_client_instance
    if _calendar_client_instance is not None:
        return _calendar_client_instance

    if settings.APP_ENV == "production" and not settings.ALLOW_FAKE_INTEGRATIONS_IN_PRODUCTION:
        if settings.CALENDAR_PROVIDER == "fake":
            raise RuntimeError(
                "Production safeguard violation: FakeCalendarClient is disabled in production."
            )

    provider = settings.CALENDAR_PROVIDER.lower().strip()
    if provider == "fake":
        _calendar_client_instance = FakeCalendarClient()
        return _calendar_client_instance
    if provider == "google":
        from fieldops.integrations.calendar.google import GoogleCalendarClient
        _calendar_client_instance = GoogleCalendarClient()
        return _calendar_client_instance
    raise ValueError(f"Unsupported calendar provider: '{provider}'")


def get_email_client() -> EmailClient:
    """Return configured email client based on settings, enforcing production safeguards."""
    global _email_client_instance
    if _email_client_instance is not None:
        return _email_client_instance

    if settings.APP_ENV == "production" and not settings.ALLOW_FAKE_INTEGRATIONS_IN_PRODUCTION:
        if settings.EMAIL_PROVIDER == "fake":
            raise RuntimeError(
                "Production safeguard violation: FakeEmailClient is disabled in production."
            )

    provider = settings.EMAIL_PROVIDER.lower().strip()
    if provider == "fake":
        _email_client_instance = FakeEmailClient()
        return _email_client_instance
    raise ValueError(f"Unsupported email provider: '{provider}'")


def set_calendar_client(client: CalendarClient | None) -> None:
    """Override calendar client instance (useful for testing)."""
    global _calendar_client_instance
    _calendar_client_instance = client


def set_email_client(client: EmailClient | None) -> None:
    """Override email client instance (useful for testing)."""
    global _email_client_instance
    _email_client_instance = client


__all__ = [
    "AuthenticationIntegrationError",
    "CalendarClient",
    "CalendarEventCreate",
    "CalendarEventResult",
    "CalendarReconciliationService",
    "EmailClient",
    "EmailSendResult",
    "FakeCalendarClient",
    "FakeEmailClient",
    "GoogleCalendarClient",
    "IntegrationError",
    "PermanentIntegrationError",
    "TransientIntegrationError",
    "get_calendar_client",
    "get_email_client",
    "set_calendar_client",
    "set_email_client",
]
