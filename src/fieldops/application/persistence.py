import logging
from sqlalchemy.orm import Session

from fieldops.db.session import SessionLocal
from fieldops.repositories.customer_repository import CustomerRepository
from fieldops.repositories.service_request_repository import (
    ServiceRequestRepository,
)

logger = logging.getLogger(__name__)


def persist_customer_and_service_request(
    customer_name: str,
    customer_email: str,
    customer_phone: str | None,
    raw_message: str,
    service_type: str,
    urgency: str,
    location: str,
    session: Session | None = None,
) -> tuple[int, int]:
    """Atomically find or create customer and persist a new service request.

    Customer Policy:
        - Unique identity key is email.
        - If customer exists with matching email, reuses the existing Customer entity.
        - If customer does not exist, creates a new Customer record.
        - Note: If name/phone differs from existing record, V1 preserves the existing
          record without auto-overwrite. Profile sync policy is deferred to Integration Phase.

    Transaction Boundary:
        Both operations execute within a single atomic database transaction.
        If either step fails, the entire transaction is rolled back, preventing
        dangling/orphaned customer or service request records.

    Returns:
        tuple[int, int]: (customer_id, service_request_id)
    """

    def _execute(s: Session) -> tuple[int, int]:
        cust_repo = CustomerRepository(s)
        sr_repo = ServiceRequestRepository(s)

        # 1. Lookup or create customer
        customer = cust_repo.get_by_email(customer_email)
        if customer is None:
            logger.info(
                "Customer not found for email=%s; creating new Customer record.",
                customer_email,
            )
            customer = cust_repo.create(
                name=customer_name or "Unknown",
                email=customer_email,
                phone=customer_phone,
            )
        else:
            logger.info(
                "Found existing customer: id=%d, email=%s (skipping name/phone overwrite per V1 policy).",
                customer.id,
                customer.email,
            )

        # 2. Create ServiceRequest
        service_request = sr_repo.create(
            customer_id=customer.id,
            raw_message=raw_message,
            service_type=service_type,
            urgency=urgency,
            location=location or "Unknown",
            status="created",
        )
        logger.info(
            "ServiceRequest created: id=%d, customer_id=%d, status=created.",
            service_request.id,
            customer.id,
        )

        return customer.id, service_request.id

    if session is not None:
        if session.in_transaction():
            with session.begin_nested():
                return _execute(session)
        else:
            with session.begin():
                return _execute(session)

    with SessionLocal() as s:
        with s.begin():
            return _execute(s)
