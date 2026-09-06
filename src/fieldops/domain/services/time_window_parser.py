from dataclasses import dataclass
from datetime import datetime, time, timedelta
import re
from zoneinfo import ZoneInfo

from fieldops.core.config import settings


@dataclass(frozen=True)
class TimeWindow:
    """Time window defining start and end boundaries for appointment scheduling."""

    start_time: datetime
    end_time: datetime


class TimeWindowParser:
    """Parser converting normalized natural language customer preferences into TimeWindow."""

    def __init__(self, tz_name: str | None = None) -> None:
        self.tz = ZoneInfo(tz_name or settings.BUSINESS_TIMEZONE)

    def parse(
        self,
        preferred_time: str | None,
        reference_time: datetime | None = None,
    ) -> TimeWindow | None:
        """Parse preferred_time into a timezone-aware TimeWindow.

        Supported V1 vocabulary (case-insensitive, whitespace-trimmed):
        - "this morning" / "today morning" -> today 09:00 - 12:00
        - "this afternoon" / "today afternoon" -> today 13:00 - 17:00
        - "this evening" / "today evening" -> today 17:00 - 20:00
        - "tomorrow morning" -> tomorrow 09:00 - 12:00
        - "tomorrow afternoon" -> tomorrow 13:00 - 17:00
        - "tomorrow evening" -> tomorrow 17:00 - 20:00
        - "YYYY-MM-DD HH:MM" -> parsed datetime to parsed datetime + duration

        Returns:
            TimeWindow if expression is recognized, else None (indicating clarification needed).
        """
        if not preferred_time or not preferred_time.strip():
            return None

        clean_text = preferred_time.strip().lower()

        # Establish current reference date in the business timezone
        now = reference_time or datetime.now(self.tz)
        if now.tzinfo is None:
            now = now.replace(tzinfo=self.tz)
        else:
            now = now.astimezone(self.tz)

        today_date = now.date()
        tomorrow_date = today_date + timedelta(days=1)

        # Standard operating window slots (Local Business Hours)
        MORNING_START = time(9, 0)
        MORNING_END = time(12, 0)
        AFTERNOON_START = time(13, 0)
        AFTERNOON_END = time(17, 0)
        EVENING_START = time(17, 0)
        EVENING_END = time(20, 0)

        # Relative keyword matching
        if clean_text in ("this morning", "today morning"):
            return TimeWindow(
                start_time=datetime.combine(today_date, MORNING_START, tzinfo=self.tz),
                end_time=datetime.combine(today_date, MORNING_END, tzinfo=self.tz),
            )
        if clean_text in ("this afternoon", "today afternoon"):
            return TimeWindow(
                start_time=datetime.combine(today_date, AFTERNOON_START, tzinfo=self.tz),
                end_time=datetime.combine(today_date, AFTERNOON_END, tzinfo=self.tz),
            )
        if clean_text in ("this evening", "today evening"):
            return TimeWindow(
                start_time=datetime.combine(today_date, EVENING_START, tzinfo=self.tz),
                end_time=datetime.combine(today_date, EVENING_END, tzinfo=self.tz),
            )
        if clean_text == "tomorrow morning":
            return TimeWindow(
                start_time=datetime.combine(tomorrow_date, MORNING_START, tzinfo=self.tz),
                end_time=datetime.combine(tomorrow_date, MORNING_END, tzinfo=self.tz),
            )
        if clean_text == "tomorrow afternoon":
            return TimeWindow(
                start_time=datetime.combine(tomorrow_date, AFTERNOON_START, tzinfo=self.tz),
                end_time=datetime.combine(tomorrow_date, AFTERNOON_END, tzinfo=self.tz),
            )
        if clean_text == "tomorrow evening":
            return TimeWindow(
                start_time=datetime.combine(tomorrow_date, EVENING_START, tzinfo=self.tz),
                end_time=datetime.combine(tomorrow_date, EVENING_END, tzinfo=self.tz),
            )

        # Match explicit ISO-like datetime format: YYYY-MM-DD HH:MM
        explicit_match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})", clean_text)
        if explicit_match:
            date_str, time_str = explicit_match.groups()
            try:
                dt_naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                start_dt = dt_naive.replace(tzinfo=self.tz)
                end_dt = start_dt + timedelta(minutes=settings.DEFAULT_APPOINTMENT_DURATION_MINUTES)
                return TimeWindow(start_time=start_dt, end_time=end_dt)
            except ValueError:
                return None

        # Unsupported relative text in V1 (e.g. "Friday after 3pm", "next week")
        return None
