"""Domain services package."""

from fieldops.domain.services.appointment_proposal import (
    AppointmentProposal,
    AppointmentProposalService,
)
from fieldops.domain.services.scheduling import (
    SchedulingResult,
    SchedulingService,
    generate_candidate_slots,
    has_time_conflict,
)
from fieldops.domain.services.technician_matching import (
    MatchingStatus,
    TechnicianMatchingResult,
    TechnicianMatchingService,
)
from fieldops.domain.services.time_window_parser import (
    TimeWindow,
    TimeWindowParser,
)

__all__ = [
    "AppointmentProposal",
    "AppointmentProposalService",
    "MatchingStatus",
    "TechnicianMatchingResult",
    "TechnicianMatchingService",
    "TimeWindow",
    "TimeWindowParser",
    "SchedulingResult",
    "SchedulingService",
    "generate_candidate_slots",
    "has_time_conflict",
]
