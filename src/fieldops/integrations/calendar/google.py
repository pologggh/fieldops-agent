"""Google Calendar API v3 adapter implementing CalendarClient protocol."""

from datetime import datetime, timezone
import json
import logging
import time
from typing import Any
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account, credentials
import google.auth
from google.auth.exceptions import DefaultCredentialsError, RefreshError

from fieldops.core.config import settings
from fieldops.integrations.calendar.base import (
    CalendarClient,
    CalendarEventCreate,
    CalendarEventResult,
)
from fieldops.integrations.exceptions import (
    AuthenticationIntegrationError,
    PermanentIntegrationError,
    TransientIntegrationError,
)
from fieldops.observability.metrics import (
    GOOGLE_CALENDAR_API_CALLS_TOTAL,
    GOOGLE_CALENDAR_LATENCY_SECONDS,
)

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


class GoogleCalendarClient(CalendarClient):
    """Google Calendar v3 adapter ensuring provider-side correlation and idempotency."""

    def __init__(self, service: Any = None) -> None:
        """Initialize Google Calendar client.

        Args:
            service: Optional pre-built Google API service resource (useful for unit testing).
        """
        self.calendar_id = settings.GOOGLE_CALENDAR_ID or "primary"
        self._dry_run = settings.GOOGLE_CALENDAR_DRY_RUN
        self._simulated_events: dict[str, dict[str, Any]] = {}

        if service is not None:
            self._service = service
        elif self._dry_run:
            logger.info("GoogleCalendarClient initialized in DRY_RUN mode; network calls simulated.")
            self._service = None
        else:
            self._service = self._init_service()

    def _init_service(self) -> Any:
        """Resolve Google credentials and build Calendar v3 service client."""
        creds = None

        # 1. Service Account JSON file
        if settings.GOOGLE_SERVICE_ACCOUNT_FILE:
            try:
                creds = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
                )
                if settings.GOOGLE_CALENDAR_DELEGATED_USER:
                    creds = creds.with_subject(settings.GOOGLE_CALENDAR_DELEGATED_USER)
                logger.info("GoogleCalendarClient: Loaded service account from file: %s", settings.GOOGLE_SERVICE_ACCOUNT_FILE)
            except Exception as exc:
                raise AuthenticationIntegrationError(
                    f"Failed to load Google service account file: {exc}",
                    provider="google_calendar",
                ) from exc

        # 2. Service Account JSON string in environment variable
        elif settings.GOOGLE_CREDENTIALS_JSON:
            try:
                account_info = json.loads(settings.GOOGLE_CREDENTIALS_JSON)
                creds = service_account.Credentials.from_service_account_info(
                    account_info, scopes=SCOPES
                )
                if settings.GOOGLE_CALENDAR_DELEGATED_USER:
                    creds = creds.with_subject(settings.GOOGLE_CALENDAR_DELEGATED_USER)
                logger.info("GoogleCalendarClient: Loaded service account from JSON environment variable")
            except Exception as exc:
                raise AuthenticationIntegrationError(
                    f"Failed to load Google credentials JSON from env: {exc}",
                    provider="google_calendar",
                ) from exc

        # 3. OAuth2 Refresh Token
        elif settings.GOOGLE_OAUTH_REFRESH_TOKEN and settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET:
            try:
                creds = credentials.Credentials(
                    token=None,
                    refresh_token=settings.GOOGLE_OAUTH_REFRESH_TOKEN,
                    client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
                    client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
                    token_uri="https://oauth2.googleapis.com/token",
                    scopes=SCOPES,
                )
                logger.info("GoogleCalendarClient: Configured OAuth2 refresh token credentials")
            except Exception as exc:
                raise AuthenticationIntegrationError(
                    f"Failed to initialize OAuth2 credentials: {exc}",
                    provider="google_calendar",
                ) from exc

        # 4. Fallback to Application Default Credentials (ADC)
        else:
            try:
                creds, _ = google.auth.default(scopes=SCOPES)
                logger.info("GoogleCalendarClient: Using Application Default Credentials (ADC)")
            except (DefaultCredentialsError, Exception) as exc:
                raise AuthenticationIntegrationError(
                    "Google Calendar credentials not configured. Please supply GOOGLE_SERVICE_ACCOUNT_FILE, "
                    "GOOGLE_CREDENTIALS_JSON, or OAuth2 refresh token.",
                    provider="google_calendar",
                ) from exc

        try:
            return build(
                "calendar",
                "v3",
                credentials=creds,
                cache_discovery=False,
            )
        except Exception as exc:
            raise AuthenticationIntegrationError(
                f"Failed to construct Google Calendar service: {exc}",
                provider="google_calendar",
            ) from exc

    @property
    def service(self) -> Any:
        return self._service

    def _ensure_timezone(self, dt: datetime) -> datetime:
        """Ensure datetime object is timezone-aware with business timezone."""
        if dt.tzinfo is None:
            tz = ZoneInfo(settings.BUSINESS_TIMEZONE)
            return dt.replace(tzinfo=tz)
        return dt

    def create_event(self, event: CalendarEventCreate) -> CalendarEventResult:
        """Create Google Calendar event with provider-side correlation and idempotency."""
        t0 = time.perf_counter()
        operation = "create_event"

        if self._dry_run:
            event_id = f"dry-run-gcal-{event.appointment_id}"
            self._simulated_events[event_id] = {
                "id": event_id,
                "summary": event.title,
                "status": "confirmed",
            }
            logger.info("GoogleCalendarClient [DRY RUN]: Simulated event creation %s", event_id)
            return CalendarEventResult(
                external_event_id=event_id,
                status="confirmed",
                provider="google_calendar",
            )

        # 1. Provider-side Idempotency Check: query by privateExtendedProperty
        try:
            list_res = (
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    privateExtendedProperty=f"fieldops_appointment_id={event.appointment_id}",
                    singleEvents=True,
                    maxResults=5,
                )
                .execute()
            )
            items = list_res.get("items", [])
            for item in items:
                if item.get("status") != "cancelled":
                    logger.info(
                        "GoogleCalendarClient: Idempotent correlation hit for appointment %s -> existing event %s",
                        event.appointment_id,
                        item.get("id"),
                    )
                    GOOGLE_CALENDAR_API_CALLS_TOTAL.labels(operation=operation, status="idempotent_hit").inc()
                    return CalendarEventResult(
                        external_event_id=item["id"],
                        status=item.get("status", "confirmed"),
                        provider="google_calendar",
                    )
        except HttpError as exc:
            # If list query fails with auth or transient error, classify and bubble up
            self._handle_http_error(exc, operation)
        except Exception as exc:
            self._handle_generic_error(exc, operation)

        # 2. Build Event Resource Body with Data Minimization
        start_aware = self._ensure_timezone(event.start_time)
        end_aware = self._ensure_timezone(event.end_time)

        clean_summary = f"FieldOps Appointment #{event.appointment_id} - {event.title}"
        clean_description = (
            f"Service Request ID: {event.appointment_id}\n"
            f"Details: {event.description or 'FieldOps Scheduled Maintenance'}"
        )

        body = {
            "summary": clean_summary,
            "description": clean_description,
            "location": event.location,
            "start": {
                "dateTime": start_aware.isoformat(),
                "timeZone": settings.BUSINESS_TIMEZONE,
            },
            "end": {
                "dateTime": end_aware.isoformat(),
                "timeZone": settings.BUSINESS_TIMEZONE,
            },
            "extendedProperties": {
                "private": {
                    "fieldops_appointment_id": str(event.appointment_id),
                    "fieldops_provider": "google_calendar",
                }
            },
        }

        # 3. Execute Insert
        try:
            created = (
                self.service.events()
                .insert(
                    calendarId=self.calendar_id,
                    body=body,
                    sendUpdates="none",  # Suppress automatic external email dispatch
                )
                .execute()
            )
            latency = time.perf_counter() - t0
            GOOGLE_CALENDAR_LATENCY_SECONDS.labels(operation=operation).observe(latency)
            GOOGLE_CALENDAR_API_CALLS_TOTAL.labels(operation=operation, status="success").inc()

            event_id = created.get("id")
            logger.info("GoogleCalendarClient: Successfully created event %s for appointment %s", event_id, event.appointment_id)
            return CalendarEventResult(
                external_event_id=event_id,
                status=created.get("status", "confirmed"),
                provider="google_calendar",
            )
        except HttpError as exc:
            self._handle_http_error(exc, operation)
        except Exception as exc:
            self._handle_generic_error(exc, operation)

    def get_event(self, external_event_id: str) -> CalendarEventResult | None:
        """Retrieve Google Calendar event by external event ID."""
        t0 = time.perf_counter()
        operation = "get_event"

        if self._dry_run:
            sim = self._simulated_events.get(external_event_id)
            if not sim:
                return None
            return CalendarEventResult(
                external_event_id=sim["id"],
                status=sim.get("status", "confirmed"),
                provider="google_calendar",
            )

        try:
            item = (
                self.service.events()
                .get(
                    calendarId=self.calendar_id,
                    eventId=external_event_id,
                )
                .execute()
            )
            latency = time.perf_counter() - t0
            GOOGLE_CALENDAR_LATENCY_SECONDS.labels(operation=operation).observe(latency)
            GOOGLE_CALENDAR_API_CALLS_TOTAL.labels(operation=operation, status="success").inc()

            return CalendarEventResult(
                external_event_id=item["id"],
                status=item.get("status", "confirmed"),
                provider="google_calendar",
            )
        except HttpError as exc:
            if exc.resp.status in (404, 410):
                logger.info("GoogleCalendarClient: Event %s not found on Google Calendar (HTTP %s)", external_event_id, exc.resp.status)
                GOOGLE_CALENDAR_API_CALLS_TOTAL.labels(operation=operation, status="not_found").inc()
                return None
            self._handle_http_error(exc, operation)
        except Exception as exc:
            self._handle_generic_error(exc, operation)

    def cancel_event(self, external_event_id: str) -> bool:
        """Cancel (delete) Google Calendar event idempotently."""
        t0 = time.perf_counter()
        operation = "cancel_event"

        if self._dry_run:
            self._simulated_events.pop(external_event_id, None)
            logger.info("GoogleCalendarClient [DRY RUN]: Simulated event deletion %s", external_event_id)
            return True

        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=external_event_id,
                sendUpdates="none",
            ).execute()
            latency = time.perf_counter() - t0
            GOOGLE_CALENDAR_LATENCY_SECONDS.labels(operation=operation).observe(latency)
            GOOGLE_CALENDAR_API_CALLS_TOTAL.labels(operation=operation, status="success").inc()
            logger.info("GoogleCalendarClient: Successfully cancelled event %s", external_event_id)
            return True
        except HttpError as exc:
            if exc.resp.status in (404, 410):
                # Idempotent deletion: target state (event removed) already satisfied
                logger.info("GoogleCalendarClient: Event %s already deleted or not found (HTTP %s). Returning True.", external_event_id, exc.resp.status)
                GOOGLE_CALENDAR_API_CALLS_TOTAL.labels(operation=operation, status="idempotent_delete").inc()
                return True
            self._handle_http_error(exc, operation)
        except Exception as exc:
            self._handle_generic_error(exc, operation)

    def test_connection(self) -> dict[str, Any]:
        """Verify API connectivity and access to the configured calendar."""
        if self._dry_run:
            return {
                "status": "connected",
                "calendar_id": self.calendar_id,
                "mode": "dry_run",
                "summary": "Dry Run Simulated Calendar",
            }

        try:
            cal = self.service.calendars().get(calendarId=self.calendar_id).execute()
            return {
                "status": "connected",
                "calendar_id": self.calendar_id,
                "summary": cal.get("summary", ""),
                "timeZone": cal.get("timeZone", ""),
            }
        except HttpError as exc:
            self._handle_http_error(exc, "test_connection")
        except Exception as exc:
            self._handle_generic_error(exc, "test_connection")

    def _handle_http_error(self, exc: HttpError, operation: str) -> None:
        """Classify Google API HttpError into Domain Integration Exceptions."""
        status = exc.resp.status
        reason = ""
        try:
            error_data = json.loads(exc.content.decode("utf-8"))
            reason = error_data.get("error", {}).get("message", "")
        except Exception:
            reason = str(exc)

        # Sanitize sensitive info from message
        sanitized_msg = f"Google Calendar API HTTP {status} during {operation}: {reason[:200]}"
        logger.warning(sanitized_msg)

        GOOGLE_CALENDAR_API_CALLS_TOTAL.labels(operation=operation, status=f"http_{status}").inc()

        # 401: Invalid or expired access credentials
        if status == 401:
            raise AuthenticationIntegrationError(
                f"Google Calendar authentication failed (401): {sanitized_msg}",
                provider="google_calendar",
            ) from exc

        # 403: Forbidden or Quota / Rate Limit
        if status == 403:
            lower_msg = reason.lower()
            if any(k in lower_msg for k in ("ratelimitexceeded", "userratelimitexceeded", "quotaexceeded")):
                raise TransientIntegrationError(
                    f"Google Calendar rate limit exceeded (403): {sanitized_msg}",
                    provider="google_calendar",
                ) from exc
            raise AuthenticationIntegrationError(
                f"Google Calendar permission denied (403): {sanitized_msg}",
                provider="google_calendar",
            ) from exc

        # 429 & 5xx: Transient server issues or throttles
        if status in (429, 500, 502, 503, 504):
            raise TransientIntegrationError(
                f"Google Calendar transient error ({status}): {sanitized_msg}",
                provider="google_calendar",
            ) from exc

        # 400, 422: Permanent client errors (malformed payload, invalid timezone format, etc.)
        if status in (400, 422):
            raise PermanentIntegrationError(
                f"Google Calendar client error ({status}): {sanitized_msg}",
                provider="google_calendar",
            ) from exc

        # Fallback to permanent
        raise PermanentIntegrationError(
            f"Google Calendar unexpected error ({status}): {sanitized_msg}",
            provider="google_calendar",
        ) from exc

    def _handle_generic_error(self, exc: Exception, operation: str) -> None:
        """Classify network, timeout, or auth library exceptions."""
        GOOGLE_CALENDAR_API_CALLS_TOTAL.labels(operation=operation, status="error").inc()

        if isinstance(exc, (RefreshError, DefaultCredentialsError)):
            raise AuthenticationIntegrationError(
                f"Google authentication credential refresh error during {operation}: {exc}",
                provider="google_calendar",
            ) from exc

        # Network timeouts and connection drops are transient
        err_str = str(exc).lower()
        if any(k in err_str for k in ("timeout", "connection refused", "reset by peer", "servernotfounderror", "temporary failure")):
            raise TransientIntegrationError(
                f"Google Calendar transient network error during {operation}: {exc}",
                provider="google_calendar",
            ) from exc

        raise PermanentIntegrationError(
            f"Google Calendar unhandled error during {operation}: {exc}",
            provider="google_calendar",
        ) from exc
