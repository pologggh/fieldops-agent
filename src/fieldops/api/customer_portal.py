"""Customer Portal API router.

Implements all customer-facing authentication and self-service endpoints:
- Customer registration & login (bcrypt hashed, separate token boundary)
- Profile management
- Service request intake, list, detail, supplement, cancel, reschedule
- Appointment list, detail, cancel
- Strict IDOR prevention: All queries filter by current_customer.id, returning 404 for unowned resources.
- Customer-friendly status mapping and data minimization.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from fieldops.core.config import settings
from fieldops.core.logging import log_operation
from fieldops.db.models import (
    Appointment,
    AuditLog,
    Customer,
    CustomerAccount,
    InboundEvent,
    OutboxEvent,
    ServiceRequest,
    Technician,
)
from fieldops.db.session import SessionLocal
from fieldops.llm.parser import parse_service_request
from fieldops.schemas.customer_schemas import (
    CustomerAppointmentView,
    CustomerAuthResponse,
    CustomerHomeSummary,
    CustomerLoginInput,
    CustomerProfileUpdateInput,
    CustomerProfileView,
    CustomerRegisterInput,
    CustomerRescheduleInput,
    CustomerServiceRequestCancelInput,
    CustomerServiceRequestCreateInput,
    CustomerServiceRequestSupplementInput,
    CustomerServiceRequestView,
    CustomerTimelineItem,
)
from fieldops.security.customer_auth import (
    create_customer_token,
    get_current_customer,
    hash_password,
    verify_password,
)
from fieldops.security.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

customer_router = APIRouter(tags=["Customer Portal"])


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def map_customer_status(internal_status: str) -> tuple[str, bool, list[str]]:
    """Map internal workflow status to customer-friendly display label and missing fields."""
    mapping = {
        "received": "Request received",
        "created": "Request received",
        "needs_information": "More information needed",
        "validated": "Finding a technician",
        "matched": "Finding a technician",
        "ready_for_scheduling": "Finding a technician",
        "waiting_for_approval": "Scheduling your visit",
        "ready_for_review": "Scheduling your visit",
        "approved": "Scheduling your visit",
        "scheduled": "Appointment scheduled",
        "appointment_created": "Appointment scheduled",
        "in_progress": "Service in progress",
        "completed": "Service completed",
        "cancelled": "Cancelled",
        "conflict": "We are reviewing your request",
        "needs_rescheduling": "We are reviewing your request",
        "reschedule_requested": "Reschedule in progress",
        "rejected": "We are reviewing alternative scheduling options.",
        "system_failed": "We are reviewing your request",
        "llm_failed": "We are reviewing your request",
        "no_technician": "We are reviewing your request",
        "no_technician_available": "We are reviewing your request",
    }
    label = mapping.get(internal_status, "We are reviewing your request")
    needs_info = internal_status == "needs_information"
    missing = ["location", "preferred_time"] if needs_info else []
    return label, needs_info, missing


def build_customer_timeline(sr: ServiceRequest, session: Session) -> list[CustomerTimelineItem]:
    """Build customer-safe timeline, strictly filtering out operator names, internal scores, and logs."""
    items: list[CustomerTimelineItem] = []

    # Initial submission
    created_ts = sr.created_at.isoformat() if sr.created_at else datetime.now(timezone.utc).isoformat()
    items.append(
        CustomerTimelineItem(
            id=f"sr-{sr.id}-init",
            timestamp=created_ts,
            title="Request Received",
            description=f"Your service request for {sr.service_type} was received.",
        )
    )

    if sr.status == "needs_information":
        items.append(
            CustomerTimelineItem(
                id=f"sr-{sr.id}-info",
                timestamp=created_ts,
                title="Information Needed",
                description="Additional details required to schedule your appointment.",
            )
        )
    elif sr.status in ["waiting_for_approval", "ready_for_review"]:
        items.append(
            CustomerTimelineItem(
                id=f"sr-{sr.id}-matching",
                timestamp=created_ts,
                title="Technician Matching",
                description="Matching suitable certified technicians for your location.",
            )
        )
    elif sr.status == "scheduled":
        items.append(
            CustomerTimelineItem(
                id=f"sr-{sr.id}-sched",
                timestamp=created_ts,
                title="Appointment Confirmed",
                description="A technician has been scheduled for your service visit.",
            )
        )
    elif sr.status == "in_progress":
        items.append(
            CustomerTimelineItem(
                id=f"sr-{sr.id}-inprogress",
                timestamp=created_ts,
                title="Service In Progress",
                description="Technician has started work on-site.",
            )
        )
    elif sr.status == "completed":
        items.append(
            CustomerTimelineItem(
                id=f"sr-{sr.id}-done",
                timestamp=created_ts,
                title="Service Completed",
                description="Service work order was successfully fulfilled.",
            )
        )
    elif sr.status == "cancelled":
        items.append(
            CustomerTimelineItem(
                id=f"sr-{sr.id}-cancel",
                timestamp=created_ts,
                title="Request Cancelled",
                description="This service request has been cancelled.",
            )
        )
    elif sr.status in ["needs_rescheduling", "reschedule_requested"]:
        items.append(
            CustomerTimelineItem(
                id=f"sr-{sr.id}-resched",
                timestamp=created_ts,
                title="Rescheduling In Progress",
                description="Your request is being rescheduled for an updated time window.",
            )
        )

    return items


def _extract_preferred_time(raw_message: str | None) -> tuple[str, str | None]:
    """Extract clean problem description and preferred time from raw_message string."""
    if not raw_message:
        return "", None
    import re
    match = re.search(r'\[Preferred Time:\s*([^\]]+)\]', raw_message)
    if match:
        pref = match.group(1).strip()
        clean = re.sub(r'\[Preferred Time:\s*[^\]]+\]', '', raw_message).strip()
        return clean, pref
    return raw_message, None


def build_customer_sr_view(sr: ServiceRequest, session: Session) -> CustomerServiceRequestView:
    """Transform ServiceRequest model to sanitized CustomerServiceRequestView DTO."""
    label, needs_info, missing = map_customer_status(sr.status)

    from fieldops.application.service_lifecycle_service import ServiceLifecycleService
    lifecycle = ServiceLifecycleService(session)

    # Appointment if any (order by latest)
    appt_view = None
    appt = (
        session.query(Appointment)
        .filter(Appointment.service_request_id == sr.id)
        .order_by(Appointment.id.desc())
        .first()
    )

    caps = lifecycle.compute_capabilities(appointment=appt, service_request=sr, role="customer")

    if appt:
        tech_name = "Field Technician"
        if appt.technician_id:
            t = session.query(Technician).filter_by(id=appt.technician_id).first()
            if t:
                tech_name = t.name

        appt_view = CustomerAppointmentView(
            id=appt.id,
            service_request_id=sr.id,
            start_time=appt.start_time.isoformat() if appt.start_time else "",
            end_time=appt.end_time.isoformat() if appt.end_time else "",
            service_type=sr.service_type or "General Service",
            location=sr.location or "",
            technician_name=tech_name,
            status=appt.status,
            can_cancel=caps.can_cancel,
            can_reschedule=caps.can_reschedule,
            started_at=appt.started_at.isoformat() if appt.started_at else None,
            completed_at=appt.completed_at.isoformat() if appt.completed_at else None,
            completion_notes=appt.completion_notes,
            resolution_summary=appt.resolution_summary,
            rescheduled_from_appointment_id=appt.rescheduled_from_appointment_id,
            replaced_by_appointment_id=appt.replaced_by_appointment_id,
        )

    timeline = build_customer_timeline(sr, session)
    clean_desc, pref_time = _extract_preferred_time(sr.raw_message)

    return CustomerServiceRequestView(
        id=sr.id,
        service_type=sr.service_type or "General Maintenance",
        problem_description=clean_desc,
        location=sr.location or "",
        preferred_time=pref_time,
        customer_status=label,
        internal_status=sr.status,
        submitted_at=sr.created_at.isoformat() if sr.created_at else "",
        needs_information=needs_info,
        missing_fields=missing,
        can_cancel=caps.can_cancel,
        can_reschedule=caps.can_reschedule,
        appointment=appt_view,
        timeline=timeline,
    )


# ==============================================================================
# 1. Customer Authentication Endpoints
# ==============================================================================


@customer_router.post(
    "/customer-auth/register",
    response_model=CustomerAuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new customer account",
)
def register_customer(
    payload: CustomerRegisterInput,
    session: Session = Depends(get_db),
) -> CustomerAuthResponse:
    """Create new Customer and CustomerAccount atomically."""
    # Check if account or customer already exists
    existing_account = (
        session.query(CustomerAccount).filter(CustomerAccount.email == payload.email).first()
    )
    if existing_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    # Check if customer record exists without account
    customer = session.query(Customer).filter(Customer.email == payload.email).first()
    if not customer:
        customer = Customer(
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
        )
        session.add(customer)
        session.flush()
    else:
        # Update name/phone if customer existed as a lead
        customer.name = payload.name
        if payload.phone:
            customer.phone = payload.phone
        session.flush()

    # Hash password with bcrypt
    pwd_hash = hash_password(payload.password)
    account = CustomerAccount(
        customer_id=customer.id,
        email=payload.email,
        password_hash=pwd_hash,
        is_active=True,
    )
    session.add(account)

    audit = AuditLog(
        entity_type="customer",
        entity_id=str(customer.id),
        action="customer.registered",
        details={"actor_type": "customer", "actor_id": str(customer.id)},
    )
    session.add(audit)
    session.commit()

    token = create_customer_token(account, customer)
    return CustomerAuthResponse(
        access_token=token,
        token_type="bearer",
        customer=CustomerProfileView(
            id=customer.id,
            name=customer.name,
            email=customer.email,
            phone=customer.phone,
        ),
    )


@customer_router.post(
    "/customer-auth/login",
    response_model=CustomerAuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Customer account login",
)
def login_customer(
    payload: CustomerLoginInput,
    request: Request,
    session: Session = Depends(get_db),
) -> CustomerAuthResponse:
    """Authenticate customer with rate limiting defense."""
    # Apply rate limiting
    rate_limiter(
        max_requests=settings.RATE_LIMIT_LOGIN_MAX_REQUESTS,
        window_seconds=settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS,
        is_auth=True,
    )(request)

    account = session.query(CustomerAccount).filter(CustomerAccount.email == payload.email).first()
    if not account or not verify_password(payload.password, account.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact support.",
        )

    customer = session.query(Customer).filter_by(id=account.customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer profile not found.",
        )

    token = create_customer_token(account, customer)
    return CustomerAuthResponse(
        access_token=token,
        token_type="bearer",
        customer=CustomerProfileView(
            id=customer.id,
            name=customer.name,
            email=customer.email,
            phone=customer.phone,
        ),
    )


# ==============================================================================
# 2. Customer Profile Endpoints
# ==============================================================================


@customer_router.get(
    "/customer/me",
    response_model=CustomerProfileView,
    summary="Get current customer profile",
)
def get_customer_profile(
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
) -> CustomerProfileView:
    """Return verified customer profile."""
    _, customer = auth
    return CustomerProfileView(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
    )


@customer_router.patch(
    "/customer/me",
    response_model=CustomerProfileView,
    summary="Update customer profile",
)
def update_customer_profile(
    payload: CustomerProfileUpdateInput,
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> CustomerProfileView:
    """Update contact details (name and phone only)."""
    _, customer = auth
    db_customer = session.query(Customer).filter_by(id=customer.id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if payload.name is not None:
        db_customer.name = payload.name.strip()
    if payload.phone is not None:
        db_customer.phone = payload.phone.strip()

    session.commit()
    session.refresh(db_customer)

    return CustomerProfileView(
        id=db_customer.id,
        name=db_customer.name,
        email=db_customer.email,
        phone=db_customer.phone,
    )


# ==============================================================================
# 3. Customer Service Request Endpoints (Strict Anti-IDOR)
# ==============================================================================


@customer_router.post(
    "/customer/requests",
    response_model=CustomerServiceRequestView,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a service request from Customer Portal",
)
def submit_customer_request(
    payload: CustomerServiceRequestCreateInput,
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> CustomerServiceRequestView:
    """Customer submits a service request. Identity is strictly derived from JWT."""
    _, customer = auth

    # Update customer phone if provided
    if payload.phone and not customer.phone:
        db_cust = session.query(Customer).filter_by(id=customer.id).first()
        if db_cust:
            db_cust.phone = payload.phone
            session.flush()

    # Parse message to identify service_type and urgency
    parsed_type = "General Service"
    parsed_urgency = "medium"
    try:
        parsed = parse_service_request(payload.problem_description)
        parsed_type = parsed.service_type
        parsed_urgency = parsed.urgency
    except Exception as e:
        logger.warning("Parser fallback on customer submit: %s", e)

    raw_message = payload.problem_description
    if payload.preferred_time:
        raw_message = f"{raw_message}\n[Preferred Time: {payload.preferred_time.strip()}]"

    loc = payload.location.strip() if payload.location else ""
    initial_status = "waiting_for_approval" if loc else "needs_information"

    from fieldops.application.policy_attribution import resolve_active_policy_attribution
    dispatch_ver, sla_ver, deadline = resolve_active_policy_attribution(session, parsed_urgency)

    # Persist ServiceRequest owned by current_customer
    sr = ServiceRequest(
        customer_id=customer.id,
        raw_message=raw_message,
        service_type=parsed_type,
        urgency=parsed_urgency,
        location=loc or "Location pending customer input",
        status=initial_status,
        dispatch_policy_version=dispatch_ver,
        sla_policy_version=sla_ver,
        sla_deadline=deadline,
    )
    session.add(sr)
    session.flush()

    # Record inbound event with source='customer_portal'
    inbound = InboundEvent(
        source="customer_portal",
        external_message_id=f"cp-{sr.id}-{int(datetime.now(timezone.utc).timestamp())}",
        request_hash=f"hash-{sr.id}",
        status="processed",
        request_id=f"cp-req-{sr.id}",
        service_request_id=sr.id,
    )
    session.add(inbound)

    # Audit log
    audit = AuditLog(
        entity_type="service_request",
        entity_id=str(sr.id),
        action="service_request.created_by_customer",
        details={
            "actor_type": "customer",
            "actor_id": str(customer.id),
            "service_type": parsed_type,
            "location": payload.location,
        },
    )
    session.add(audit)
    session.commit()
    session.refresh(sr)

    return build_customer_sr_view(sr, session)


@customer_router.get(
    "/customer/requests",
    response_model=List[CustomerServiceRequestView],
    summary="List own service requests",
)
def list_customer_requests(
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> List[CustomerServiceRequestView]:
    """Retrieve only requests belonging to current customer (Anti-IDOR)."""
    _, customer = auth
    requests = (
        session.query(ServiceRequest)
        .filter(ServiceRequest.customer_id == customer.id)
        .order_by(ServiceRequest.id.desc())
        .all()
    )
    return [build_customer_sr_view(sr, session) for sr in requests]


@customer_router.get(
    "/customer/requests/{id}",
    response_model=CustomerServiceRequestView,
    summary="Get single service request detail",
)
def get_customer_request(
    id: int,
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> CustomerServiceRequestView:
    """Anti-IDOR: Return 404 if request does not exist OR does not belong to current customer."""
    _, customer = auth
    sr = (
        session.query(ServiceRequest)
        .filter(ServiceRequest.id == id, ServiceRequest.customer_id == customer.id)
        .first()
    )
    if not sr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found.",
        )

    return build_customer_sr_view(sr, session)


@customer_router.post(
    "/customer/requests/{id}/supplement",
    response_model=CustomerServiceRequestView,
    summary="Supplement missing information on a service request",
)
def supplement_customer_request(
    id: int,
    payload: CustomerServiceRequestSupplementInput,
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> CustomerServiceRequestView:
    """Provide missing details and resume processing without creating duplicate work orders."""
    _, customer = auth
    sr = (
        session.query(ServiceRequest)
        .filter(ServiceRequest.id == id, ServiceRequest.customer_id == customer.id)
        .first()
    )
    if not sr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found.",
        )

    if sr.status in ["completed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot update details for a completed or cancelled request.",
        )

    # Apply supplemented fields
    if payload.location:
        sr.location = payload.location.strip()
    if payload.preferred_time:
        clean_desc, _ = _extract_preferred_time(sr.raw_message)
        sr.raw_message = f"{clean_desc}\n[Preferred Time: {payload.preferred_time.strip()}]"
    if payload.additional_details:
        sr.raw_message = f"{sr.raw_message}\n[Customer Note: {payload.additional_details.strip()}]"

    # If it was waiting for information, advance to ready_for_scheduling / waiting_for_approval
    if sr.status == "needs_information":
        sr.status = "waiting_for_approval"

    audit = AuditLog(
        entity_type="service_request",
        entity_id=str(sr.id),
        action="service_request.information_added",
        details={
            "actor_type": "customer",
            "actor_id": str(customer.id),
            "supplemented_fields": [k for k, v in payload.dict().items() if v is not None],
        },
    )
    session.add(audit)
    session.commit()
    session.refresh(sr)

    return build_customer_sr_view(sr, session)


@customer_router.post(
    "/customer/requests/{id}/cancel",
    response_model=CustomerServiceRequestView,
    summary="Cancel a service request",
)
def cancel_customer_request(
    id: int,
    payload: CustomerServiceRequestCancelInput,
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> CustomerServiceRequestView:
    """Customer cancels a service request if not in non-cancellable state."""
    _, customer = auth
    sr = (
        session.query(ServiceRequest)
        .filter(ServiceRequest.id == id, ServiceRequest.customer_id == customer.id)
        .first()
    )
    if not sr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found.",
        )

    from fieldops.application.service_lifecycle_service import ServiceLifecycleService
    lifecycle = ServiceLifecycleService(session)
    lifecycle.cancel_request(
        service_request_id=sr.id,
        reason=payload.reason or "Cancelled by customer",
        actor_type="customer",
        actor_id=str(customer.id),
    )
    session.commit()
    session.refresh(sr)

    return build_customer_sr_view(sr, session)


@customer_router.post(
    "/customer/requests/{id}/reschedule",
    response_model=CustomerServiceRequestView,
    summary="Request rescheduling of a service request",
)
def reschedule_customer_request(
    id: int,
    payload: CustomerRescheduleInput,
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> CustomerServiceRequestView:
    """Request appointment rescheduling. Triggers redispatch/approval workflow."""
    _, customer = auth
    sr = (
        session.query(ServiceRequest)
        .filter(ServiceRequest.id == id, ServiceRequest.customer_id == customer.id)
        .first()
    )
    if not sr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found.",
        )

    from fieldops.application.service_lifecycle_service import ServiceLifecycleService
    lifecycle = ServiceLifecycleService(session)
    clean_desc, _ = _extract_preferred_time(sr.raw_message)
    sr.raw_message = f"{clean_desc}\n[Preferred Time: {payload.preferred_time.strip()}]"

    lifecycle.request_reschedule(
        service_request_id=sr.id,
        preferred_time=payload.preferred_time,
        reason=payload.reason,
        requested_by_type="customer",
        requested_by_id=str(customer.id),
    )
    session.commit()
    session.refresh(sr)

    return build_customer_sr_view(sr, session)


# ==============================================================================
# 4. Customer Appointments Endpoints (Anti-IDOR)
# ==============================================================================


@customer_router.get(
    "/customer/appointments",
    response_model=List[CustomerAppointmentView],
    summary="List customer's confirmed appointments",
)
def list_customer_appointments(
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> List[CustomerAppointmentView]:
    """Retrieve only appointments linked to current customer's requests."""
    _, customer = auth
    appts = (
        session.query(Appointment)
        .join(ServiceRequest, Appointment.service_request_id == ServiceRequest.id)
        .filter(ServiceRequest.customer_id == customer.id)
        .order_by(Appointment.start_time.asc())
        .all()
    )

    result: list[CustomerAppointmentView] = []
    for appt in appts:
        sr = session.query(ServiceRequest).filter_by(id=appt.service_request_id).first()
        tech_name = "Field Technician"
        if appt.technician_id:
            t = session.query(Technician).filter_by(id=appt.technician_id).first()
            if t:
                tech_name = t.name

        result.append(
            CustomerAppointmentView(
                id=appt.id,
                service_request_id=appt.service_request_id,
                start_time=appt.start_time.isoformat() if appt.start_time else "",
                end_time=appt.end_time.isoformat() if appt.end_time else "",
                service_type=sr.service_type if sr else "Field Service",
                location=sr.location if sr else "",
                technician_name=tech_name,
                status=appt.status,
                can_cancel=appt.status not in ["completed", "cancelled", "in_progress"],
                can_reschedule=appt.status not in ["completed", "cancelled", "in_progress"],
            )
        )

    return result


@customer_router.get(
    "/customer/appointments/{id}",
    response_model=CustomerAppointmentView,
    summary="Get appointment details",
)
def get_customer_appointment(
    id: int,
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> CustomerAppointmentView:
    """Anti-IDOR: Return 404 if appointment not found or not owned by customer."""
    _, customer = auth
    appt = (
        session.query(Appointment)
        .join(ServiceRequest, Appointment.service_request_id == ServiceRequest.id)
        .filter(Appointment.id == id, ServiceRequest.customer_id == customer.id)
        .first()
    )
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    sr = session.query(ServiceRequest).filter_by(id=appt.service_request_id).first()
    tech_name = "Field Technician"
    if appt.technician_id:
        t = session.query(Technician).filter_by(id=appt.technician_id).first()
        if t:
            tech_name = t.name

    return CustomerAppointmentView(
        id=appt.id,
        service_request_id=appt.service_request_id,
        start_time=appt.start_time.isoformat() if appt.start_time else "",
        end_time=appt.end_time.isoformat() if appt.end_time else "",
        service_type=sr.service_type if sr else "Field Service",
        location=sr.location if sr else "",
        technician_name=tech_name,
        status=appt.status,
        can_cancel=appt.status not in ["completed", "cancelled", "in_progress"],
        can_reschedule=appt.status not in ["completed", "cancelled", "in_progress"],
    )


@customer_router.post(
    "/customer/appointments/{id}/cancel",
    response_model=CustomerAppointmentView,
    summary="Cancel an appointment",
)
def cancel_customer_appointment(
    id: int,
    payload: CustomerServiceRequestCancelInput,
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> CustomerAppointmentView:
    """Cancel a scheduled appointment."""
    _, customer = auth
    appt = (
        session.query(Appointment)
        .join(ServiceRequest, Appointment.service_request_id == ServiceRequest.id)
        .filter(Appointment.id == id, ServiceRequest.customer_id == customer.id)
        .first()
    )
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    if appt.status in ["completed", "cancelled", "in_progress"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Appointment cannot be cancelled in its current state.",
        )

    appt.status = "cancelled"
    sr = session.query(ServiceRequest).filter_by(id=appt.service_request_id).first()
    if sr:
        sr.status = "cancelled"

    outbox = OutboxEvent(
        event_type="appointment.cancelled",
        aggregate_type="appointment",
        aggregate_id=str(appt.id),
        payload={"appointment_id": appt.id, "reason": payload.reason or "Cancelled by customer"},
    )
    session.add(outbox)

    audit = AuditLog(
        entity_type="appointment",
        entity_id=str(appt.id),
        action="appointment.cancelled_by_customer",
        details={
            "actor_type": "customer",
            "actor_id": str(customer.id),
            "reason": payload.reason or "Cancelled by customer",
        },
    )
    session.add(audit)
    session.commit()
    session.refresh(appt)

    tech_name = "Field Technician"
    if appt.technician_id:
        t = session.query(Technician).filter_by(id=appt.technician_id).first()
        if t:
            tech_name = t.name

    return CustomerAppointmentView(
        id=appt.id,
        service_request_id=appt.service_request_id,
        start_time=appt.start_time.isoformat() if appt.start_time else "",
        end_time=appt.end_time.isoformat() if appt.end_time else "",
        service_type=sr.service_type if sr else "Field Service",
        location=sr.location if sr else "",
        technician_name=tech_name,
        status=appt.status,
        can_cancel=False,
        can_reschedule=False,
    )


# ==============================================================================
# 5. Customer Home Summary Endpoint
# ==============================================================================


@customer_router.get(
    "/customer/summary",
    response_model=CustomerHomeSummary,
    summary="Get customer dashboard home summary",
)
def get_customer_summary(
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> CustomerHomeSummary:
    """Return customer home statistics and active appointments."""
    _, customer = auth

    # Open requests
    open_reqs = (
        session.query(ServiceRequest)
        .filter(
            ServiceRequest.customer_id == customer.id,
            ServiceRequest.status.notin_(["completed", "cancelled"]),
        )
        .order_by(ServiceRequest.id.desc())
        .all()
    )

    needs_info_count = sum(1 for r in open_reqs if r.status == "needs_information")

    # Upcoming appointment
    now_utc = datetime.now(timezone.utc)
    upcoming_appt_m = (
        session.query(Appointment)
        .join(ServiceRequest, Appointment.service_request_id == ServiceRequest.id)
        .filter(
            ServiceRequest.customer_id == customer.id,
            Appointment.status == "scheduled",
            Appointment.start_time >= now_utc,
        )
        .order_by(Appointment.start_time.asc())
        .first()
    )

    upcoming_view = None
    if upcoming_appt_m:
        sr = session.query(ServiceRequest).filter_by(id=upcoming_appt_m.service_request_id).first()
        t = (
            session.query(Technician).filter_by(id=upcoming_appt_m.technician_id).first()
            if upcoming_appt_m.technician_id
            else None
        )
        upcoming_view = CustomerAppointmentView(
            id=upcoming_appt_m.id,
            service_request_id=upcoming_appt_m.service_request_id,
            start_time=upcoming_appt_m.start_time.isoformat() if upcoming_appt_m.start_time else "",
            end_time=upcoming_appt_m.end_time.isoformat() if upcoming_appt_m.end_time else "",
            service_type=sr.service_type if sr else "Service Visit",
            location=sr.location if sr else "",
            technician_name=t.name if t else "Assigned Technician",
            status=upcoming_appt_m.status,
            can_cancel=True,
            can_reschedule=True,
        )

    recent_views = [build_customer_sr_view(sr, session) for sr in open_reqs[:5]]

    return CustomerHomeSummary(
        open_requests_count=len(open_reqs),
        needs_info_count=needs_info_count,
        active_requests_count=len(open_reqs),
        upcoming_appointments_count=1 if upcoming_view else 0,
        needs_action_count=needs_info_count,
        upcoming_appointment=upcoming_view,
        recent_requests=recent_views,
    )
