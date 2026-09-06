"""Unit tests for GoogleCalendarClient adapter, error classification, idempotency, and admin endpoints."""

from datetime import datetime, timezone
import json
from unittest.mock import MagicMock, patch
import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from fieldops.core.config import settings
from fieldops.integrations import (
    AuthenticationIntegrationError,
    CalendarEventCreate,
    FakeCalendarClient,
    GoogleCalendarClient,
    PermanentIntegrationError,
    TransientIntegrationError,
    get_calendar_client,
    set_calendar_client,
)


def _make_http_error(status_code: int, message: str = "Error message", reason: str = "Error") -> HttpError:
    """Helper to build a realistic Google API HttpError."""
    resp = Response({"status": str(status_code), "reason": reason})
    content = json.dumps({"error": {"code": status_code, "message": message, "status": reason}}).encode("utf-8")
    return HttpError(resp, content)


class TestGoogleCalendarPayloadMapping:
    """Validate data minimization, formatting, and timezone handling."""

    def test_create_event_mapping_and_timezone(self) -> None:
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.list.return_value.execute.return_value = {"items": []}
        mock_events.insert.return_value.execute.return_value = {
            "id": "gcal-event-12345",
            "status": "confirmed",
        }

        client = GoogleCalendarClient(service=mock_service)
        event_dto = CalendarEventCreate(
            appointment_id=42,
            title="HVAC Filter Replacement",
            start_time=datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 15, 16, 0, tzinfo=timezone.utc),
            location="Tokyo Minato-ku 1-2-3",
            description="Replace HEPA filters and sanitize intake vents",
        )

        result = client.create_event(event_dto)

        assert result.external_event_id == "gcal-event-12345"
        assert result.status == "confirmed"
        assert result.provider == "google_calendar"

        # Verify insert payload
        mock_events.insert.assert_called_once()
        call_kwargs = mock_events.insert.call_args[1]
        body = call_kwargs["body"]

        assert body["summary"] == "FieldOps Appointment #42 - HVAC Filter Replacement"
        assert "Service Request ID: 42" in body["description"]
        assert body["location"] == "Tokyo Minato-ku 1-2-3"
        assert body["extendedProperties"]["private"]["fieldops_appointment_id"] == "42"
        assert body["extendedProperties"]["private"]["fieldops_provider"] == "google_calendar"
        assert call_kwargs["sendUpdates"] == "none"  # Crucial: no external email spam


class TestGoogleCalendarIdempotency:
    """Validate provider-side correlation and deduplication."""

    def test_create_event_idempotency_lookup_hit_avoids_duplicate(self) -> None:
        mock_service = MagicMock()
        # Mock list returning existing active event
        mock_service.events().list().execute.return_value = {
            "items": [
                {
                    "id": "existing-event-999",
                    "status": "confirmed",
                    "summary": "Existing Event",
                }
            ]
        }

        client = GoogleCalendarClient(service=mock_service)
        event_dto = CalendarEventCreate(
            appointment_id=77,
            title="Plumbing Inspection",
            start_time=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 20, 11, 0, tzinfo=timezone.utc),
            location="Shibuya 5-6-7",
            description="Water leak inspection",
        )

        result = client.create_event(event_dto)

        # Asserts: returned existing event without inserting!
        assert result.external_event_id == "existing-event-999"
        assert result.status == "confirmed"
        mock_service.events().insert.assert_not_called()


class TestGoogleCalendarCancellation:
    """Validate idempotent cancellation and 404 handling."""

    def test_cancel_event_success(self) -> None:
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.delete.return_value.execute.return_value = ""

        client = GoogleCalendarClient(service=mock_service)
        res = client.cancel_event("evt-to-cancel")
        assert res is True
        mock_events.delete.assert_called_once()

    def test_cancel_event_404_idempotent_success(self) -> None:
        mock_service = MagicMock()
        mock_service.events().delete().execute.side_effect = _make_http_error(404, "Event not found")

        client = GoogleCalendarClient(service=mock_service)
        res = client.cancel_event("already-deleted-event")
        # 404 should return True because target state (event removed) is satisfied
        assert res is True

    def test_get_event_404_returns_none(self) -> None:
        mock_service = MagicMock()
        mock_service.events().get().execute.side_effect = _make_http_error(404, "Not Found")

        client = GoogleCalendarClient(service=mock_service)
        res = client.get_event("nonexistent-event")
        assert res is None


class TestGoogleCalendarErrorClassification:
    """Verify HTTP and network error classification."""

    def test_401_classified_as_authentication_error(self) -> None:
        mock_service = MagicMock()
        mock_service.events().insert().execute.side_effect = _make_http_error(401, "Invalid Credentials")
        mock_service.events().list().execute.return_value = {"items": []}

        client = GoogleCalendarClient(service=mock_service)
        event_dto = CalendarEventCreate(
            appointment_id=1,
            title="Test",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            location="Tokyo",
        )

        with pytest.raises(AuthenticationIntegrationError) as exc_info:
            client.create_event(event_dto)
        assert exc_info.value.retryable is False

    def test_403_rate_limit_classified_as_transient_error(self) -> None:
        mock_service = MagicMock()
        mock_service.events().insert().execute.side_effect = _make_http_error(
            403, "User rate limit exceeded: rateLimitExceeded"
        )
        mock_service.events().list().execute.return_value = {"items": []}

        client = GoogleCalendarClient(service=mock_service)
        event_dto = CalendarEventCreate(
            appointment_id=1,
            title="Test",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            location="Tokyo",
        )

        with pytest.raises(TransientIntegrationError) as exc_info:
            client.create_event(event_dto)
        assert exc_info.value.retryable is True

    def test_403_permission_denied_classified_as_auth_error(self) -> None:
        mock_service = MagicMock()
        mock_service.events().insert().execute.side_effect = _make_http_error(
            403, "The user does not have permission to modify this calendar."
        )
        mock_service.events().list().execute.return_value = {"items": []}

        client = GoogleCalendarClient(service=mock_service)
        event_dto = CalendarEventCreate(
            appointment_id=1,
            title="Test",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            location="Tokyo",
        )

        with pytest.raises(AuthenticationIntegrationError) as exc_info:
            client.create_event(event_dto)
        assert exc_info.value.retryable is False

    def test_503_classified_as_transient_error(self) -> None:
        mock_service = MagicMock()
        mock_service.events().insert().execute.side_effect = _make_http_error(503, "Backend Error")
        mock_service.events().list().execute.return_value = {"items": []}

        client = GoogleCalendarClient(service=mock_service)
        event_dto = CalendarEventCreate(
            appointment_id=1,
            title="Test",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            location="Tokyo",
        )

        with pytest.raises(TransientIntegrationError) as exc_info:
            client.create_event(event_dto)
        assert exc_info.value.retryable is True

    def test_400_bad_request_classified_as_permanent_error(self) -> None:
        mock_service = MagicMock()
        mock_service.events().insert().execute.side_effect = _make_http_error(400, "Invalid datetime format")
        mock_service.events().list().execute.return_value = {"items": []}

        client = GoogleCalendarClient(service=mock_service)
        event_dto = CalendarEventCreate(
            appointment_id=1,
            title="Test",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            location="Tokyo",
        )

        with pytest.raises(PermanentIntegrationError) as exc_info:
            client.create_event(event_dto)
        assert exc_info.value.retryable is False


class TestGoogleCalendarDryRunMode:
    """Verify dry run simulation behaves deterministically without network calls."""

    def test_dry_run_create_and_delete(self) -> None:
        with patch.object(settings, "GOOGLE_CALENDAR_DRY_RUN", True):
            client = GoogleCalendarClient()
            event_dto = CalendarEventCreate(
                appointment_id=888,
                title="Dry Run Test",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                location="Tokyo",
            )
            res = client.create_event(event_dto)
            assert res.external_event_id == "dry-run-gcal-888"
            assert res.provider == "google_calendar"

            # Check get_event
            fetched = client.get_event("dry-run-gcal-888")
            assert fetched is not None
            assert fetched.external_event_id == "dry-run-gcal-888"

            # Check cancel_event
            assert client.cancel_event("dry-run-gcal-888") is True
            assert client.get_event("dry-run-gcal-888") is None


class TestProviderFactoryAndProductionGuard:
    """Test get_calendar_client provider routing and production guard enforcement."""

    def test_provider_factory_routing(self) -> None:
        set_calendar_client(None)
        with patch.object(settings, "CALENDAR_PROVIDER", "fake"):
            client = get_calendar_client()
            assert isinstance(client, FakeCalendarClient)

        set_calendar_client(None)
        with patch.object(settings, "CALENDAR_PROVIDER", "google"), patch.object(settings, "GOOGLE_CALENDAR_DRY_RUN", True):
            client = get_calendar_client()
            assert isinstance(client, GoogleCalendarClient)
        set_calendar_client(None)

    def test_production_guard_rejects_fake_calendar_in_production(self) -> None:
        set_calendar_client(None)
        with patch.object(settings, "APP_ENV", "production"), patch.object(
            settings, "ALLOW_FAKE_INTEGRATIONS_IN_PRODUCTION", False
        ), patch.object(settings, "CALENDAR_PROVIDER", "fake"):
            with pytest.raises(RuntimeError, match="Production safeguard violation"):
                get_calendar_client()
        set_calendar_client(None)
