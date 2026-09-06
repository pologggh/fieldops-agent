"""Fake in-memory calendar client for development and automated testing."""

import logging
from typing import Any

from fieldops.integrations.calendar.base import (
    CalendarClient,
    CalendarEventCreate,
    CalendarEventResult,
)
from fieldops.integrations.exceptions import (
    PermanentIntegrationError,
    TransientIntegrationError,
)

logger = logging.getLogger(__name__)


class FakeCalendarClient(CalendarClient):
    """Simulated calendar provider with deterministic IDs and fault injection hooks."""

    def __init__(self) -> None:
        self._events: dict[str, CalendarEventResult] = {}
        self._transient_failure_countdown: int = 0
        self._permanent_failure_active: bool = False
        self._failure_message: str = ""
        self.call_count: int = 0

    def simulate_transient_failure(
        self, count: int = 1, message: str = "Simulated temporary calendar outage (503)"
    ) -> None:
        """Inject transient failures that fail count times before succeeding."""
        self._transient_failure_countdown = count
        self._failure_message = message

    def simulate_permanent_failure(
        self, message: str = "Simulated permanent calendar error (400 Bad Request)"
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
        """Clear in-memory state and simulated failures."""
        self._events.clear()
        self.reset_simulation()
        self.call_count = 0

    def create_event(self, event: CalendarEventCreate) -> CalendarEventResult:
        """Create simulated calendar event with deterministic external_event_id."""
        self.call_count += 1

        if self._permanent_failure_active:
            logger.warning("FakeCalendarClient: Raising simulated permanent failure")
            raise PermanentIntegrationError(
                self._failure_message or "Simulated permanent calendar error",
                provider="fake_calendar",
            )

        if self._transient_failure_countdown > 0:
            self._transient_failure_countdown -= 1
            logger.warning("FakeCalendarClient: Raising simulated transient failure (remaining: %d)", self._transient_failure_countdown)
            raise TransientIntegrationError(
                self._failure_message or "Simulated transient calendar network timeout",
                provider="fake_calendar",
            )

        # Provider-side idempotency: deterministic event ID based on appointment_id
        external_id = f"fake-cal-appointment-{event.appointment_id}"

        if external_id in self._events:
            logger.info("FakeCalendarClient: Idempotent hit for %s", external_id)
            return self._events[external_id]

        res = CalendarEventResult(
            external_event_id=external_id,
            status="confirmed",
            provider="fake_calendar",
        )
        self._events[external_id] = res
        logger.info("FakeCalendarClient: Created event %s for appointment %s", external_id, event.appointment_id)
        return res

    def get_event(self, external_event_id: str) -> CalendarEventResult | None:
        """Retrieve simulated event by ID."""
        return self._events.get(external_event_id)

    def cancel_event(self, external_event_id: str) -> bool:
        """Mark simulated event as cancelled."""
        self.call_count += 1

        if self._permanent_failure_active:
            raise PermanentIntegrationError(
                self._failure_message or "Simulated permanent calendar cancellation error",
                provider="fake_calendar",
            )

        if self._transient_failure_countdown > 0:
            self._transient_failure_countdown -= 1
            raise TransientIntegrationError(
                self._failure_message or "Simulated transient calendar cancellation timeout",
                provider="fake_calendar",
            )

        if external_event_id in self._events:
            existing = self._events[external_event_id]
            self._events[external_event_id] = CalendarEventResult(
                external_event_id=existing.external_event_id,
                status="cancelled",
                provider="fake_calendar",
            )
            logger.info("FakeCalendarClient: Cancelled event %s", external_event_id)
            return True

        # Idempotent cancel: return True even if not in dict
        logger.info("FakeCalendarClient: Cancelled unknown event %s (idempotent)", external_event_id)
        return True
