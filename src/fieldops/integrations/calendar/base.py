"""Calendar integration contract and data transfer objects."""

from abc import ABC, abstractmethod
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class CalendarEventCreate(BaseModel):
    """Parameters for creating an external calendar event."""

    model_config = ConfigDict(frozen=True)

    appointment_id: int
    title: str
    start_time: datetime
    end_time: datetime
    location: str
    description: str | None = None


class CalendarEventResult(BaseModel):
    """Normalized result returned by calendar provider."""

    model_config = ConfigDict(frozen=True)

    external_event_id: str
    status: str
    provider: str = "fake_calendar"


class CalendarClient(ABC):
    """Abstract boundary protocol for calendar providers."""

    @abstractmethod
    def create_event(self, event: CalendarEventCreate) -> CalendarEventResult:
        """Create calendar event, ensuring provider-side idempotency."""
        pass

    @abstractmethod
    def get_event(self, external_event_id: str) -> CalendarEventResult | None:
        """Fetch existing calendar event by external ID."""
        pass

    @abstractmethod
    def cancel_event(self, external_event_id: str) -> bool:
        """Cancel or remove an existing calendar event."""
        pass
