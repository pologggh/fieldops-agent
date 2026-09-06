from sqlalchemy.orm import Session

from fieldops.db.models import ServiceRequest


class ServiceRequestRepository:
    """Repository for ServiceRequest persistence and data access."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, service_request_id: int) -> ServiceRequest | None:
        """Fetch a service request by its primary key ID."""
        return self.session.get(ServiceRequest, service_request_id)

    def create(
        self,
        customer_id: int,
        raw_message: str,
        service_type: str,
        urgency: str,
        location: str,
        status: str = "created",
    ) -> ServiceRequest:
        """Create and flush a new ServiceRequest entity into the session.

        Does not commit directly so the caller can coordinate atomic multi-entity transactions.
        """
        from fieldops.application.policy_attribution import resolve_active_policy_attribution
        dispatch_ver, sla_ver, deadline = resolve_active_policy_attribution(self.session, urgency)

        service_request = ServiceRequest(
            customer_id=customer_id,
            raw_message=raw_message,
            service_type=service_type,
            urgency=urgency,
            location=location,
            status=status,
            dispatch_policy_version=dispatch_ver,
            sla_policy_version=sla_ver,
            sla_deadline=deadline,
        )
        self.session.add(service_request)
        self.session.flush()
        return service_request

    def update_status(
        self, service_request_id: int, status: str
    ) -> ServiceRequest | None:
        """Update the status of a service request and flush the session."""
        service_request = self.get_by_id(service_request_id)
        if service_request is not None:
            service_request.status = status
            self.session.flush()
        return service_request
