"""Policy version attribution and SLA deadline calculation helper."""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from fieldops.db.models import DispatchPolicy, SLAPolicy


def resolve_active_policy_attribution(
    session: Session, urgency: Optional[str] = None
) -> Tuple[Optional[int], Optional[int], datetime]:
    """Snapshot active DispatchPolicy version, SLAPolicy version, and compute SLA deadline.

    Returns:
        (dispatch_policy_version, sla_policy_version, sla_deadline)
    """
    dispatch_ver = None
    sla_ver = None
    now_utc = datetime.now(timezone.utc)
    deadline = now_utc + timedelta(hours=24)

    try:
        active_dispatch = (
            session.query(DispatchPolicy).filter_by(is_active=True).first()
        )
        if active_dispatch:
            dispatch_ver = active_dispatch.version

        active_sla = session.query(SLAPolicy).filter_by(is_active=True).first()
        if active_sla and active_sla.targets:
            sla_ver = active_sla.version
            urgency_map = {
                "emergency": "P0",
                "high": "P1",
                "medium": "P2",
                "low": "P3",
            }
            tier = urgency_map.get((urgency or "medium").lower(), "P2")
            tier_cfg = active_sla.targets.get(tier, {})
            mins = (
                tier_cfg.get("service_start_minutes")
                or tier_cfg.get("response_minutes")
                or (24 * 60)
            )
            deadline = now_utc + timedelta(minutes=mins)
        else:
            default_hours = {"emergency": 4, "high": 8, "medium": 24, "low": 48}
            hrs = default_hours.get((urgency or "medium").lower(), 24)
            deadline = now_utc + timedelta(hours=hrs)
    except Exception:
        pass

    return dispatch_ver, sla_ver, deadline
