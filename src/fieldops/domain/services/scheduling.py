from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from fieldops.core.config import settings
from fieldops.domain.services.time_window_parser import TimeWindow
from fieldops.repositories.appointment_repository import AppointmentRepository

from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def ensure_timezone(dt: datetime, tz_name: str | None = None) -> datetime:
    """Normalize datetime to be timezone-aware in the configured business timezone."""
    tz = ZoneInfo(tz_name or settings.BUSINESS_TIMEZONE)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def has_time_conflict(
    slot_start: datetime,
    slot_end: datetime,
    existing_start: datetime,
    existing_end: datetime,
) -> bool:
    """Determine whether two time intervals overlap.

    Deterministic formula:
        existing_start < slot_end AND existing_end > slot_start
    All datetimes are normalized to timezone-aware timestamps before comparison.
    """
    s_start = ensure_timezone(slot_start)
    s_end = ensure_timezone(slot_end)
    e_start = ensure_timezone(existing_start)
    e_end = ensure_timezone(existing_end)

    return e_start < s_end and e_end > s_start


def generate_candidate_slots(
    window: TimeWindow,
    duration_minutes: int | None = None,
    step_minutes: int | None = None,
) -> list[TimeWindow]:
    """Generate potential appointment time slots within a given window.

    Args:
        window: Bounding TimeWindow.
        duration_minutes: Service duration in minutes (defaults to settings.DEFAULT_APPOINTMENT_DURATION_MINUTES).
        step_minutes: Sliding interval step in minutes (defaults to settings.DEFAULT_SLOT_STEP_MINUTES).

    Returns:
        List of TimeWindow candidate slots that fit completely within the window.
    """
    duration = timedelta(
        minutes=duration_minutes or settings.DEFAULT_APPOINTMENT_DURATION_MINUTES
    )
    step = timedelta(minutes=step_minutes or settings.DEFAULT_SLOT_STEP_MINUTES)

    slots: list[TimeWindow] = []
    current_start = window.start_time

    while current_start + duration <= window.end_time:
        slots.append(
            TimeWindow(
                start_time=current_start,
                end_time=current_start + duration,
            )
        )
        current_start += step

    return slots


@dataclass(frozen=True)
class SchedulingResult:
    """Result of schedule availability checking."""

    available_options: list[dict[str, Any]]
    scheduling_status: str


class SchedulingService:
    """Domain service evaluating technician schedule availability against existing appointments."""

    def __init__(self, appointment_repo: AppointmentRepository) -> None:
        self.appointment_repo = appointment_repo

    def check_availability(
        self,
        candidate_technician_ids: list[int],
        window: TimeWindow,
        duration_minutes: int | None = None,
        step_minutes: int | None = None,
    ) -> SchedulingResult:
        """Find non-conflicting appointment slots for candidate technicians in the requested window.

        Args:
            candidate_technician_ids: List of qualified technician IDs.
            window: Customer's requested target TimeWindow.
            duration_minutes: Estimated service duration.
            step_minutes: Interval step between potential start times.

        Returns:
            SchedulingResult containing available options and status.
        """
        if not candidate_technician_ids:
            logger.info("Scheduling check skipped: no candidate technicians provided.")
            return SchedulingResult(
                available_options=[],
                scheduling_status="no_available_slots",
            )

        candidate_slots = generate_candidate_slots(
            window,
            duration_minutes=duration_minutes,
            step_minutes=step_minutes,
        )

        if not candidate_slots:
            logger.info(
                "No candidate slots could be generated for window %s - %s",
                window.start_time,
                window.end_time,
            )
            return SchedulingResult(
                available_options=[],
                scheduling_status="no_available_slots",
            )

        available_options: list[dict[str, Any]] = []

        for tech_id in candidate_technician_ids:
            # Query active blocking appointments for technician overlapping window
            existing_appointments = (
                self.appointment_repo.get_blocking_by_technician_and_window(
                    technician_id=tech_id,
                    window_start=window.start_time,
                    window_end=window.end_time,
                )
            )

            for slot in candidate_slots:
                # Check for conflict against all blocking existing appointments
                conflict_found = False
                for appt in existing_appointments:
                    if has_time_conflict(
                        slot_start=slot.start_time,
                        slot_end=slot.end_time,
                        existing_start=appt.start_time,
                        existing_end=appt.end_time,
                    ):
                        conflict_found = True
                        break

                if not conflict_found:
                    available_options.append(
                        {
                            "technician_id": tech_id,
                            "start_time": slot.start_time.isoformat(),
                            "end_time": slot.end_time.isoformat(),
                        }
                    )

        if not available_options:
            logger.info("All candidate slots conflicted with existing appointments.")
            return SchedulingResult(
                available_options=[],
                scheduling_status="no_available_slots",
            )

        logger.info(
            "Found %d available appointment slot option(s).",
            len(available_options),
        )
        return SchedulingResult(
            available_options=available_options,
            scheduling_status="schedule_options_ready",
        )
