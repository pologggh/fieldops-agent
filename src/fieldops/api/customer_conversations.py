"""Customer Conversational Intake API router.

Endpoints:
- POST /customer/conversations: Initialize a new intake conversation
- GET /customer/conversations: List conversations belonging to the authenticated customer
- GET /customer/conversations/{id}: Get conversation detail with messages and draft
- POST /customer/conversations/{id}/messages: Send message, run parser, update draft
- POST /customer/conversations/{id}/confirm: Explicitly convert complete draft to formal ServiceRequest
- POST /customer/conversations/{id}/cancel: Cancel active conversation without creating ticket
"""

from datetime import datetime, timezone
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from fieldops.conversation.agent_engine import process_turn
from fieldops.core.exceptions import ConflictError
from fieldops.db.models import (
    AuditLog,
    Conversation,
    ConversationMessage,
    Customer,
    CustomerAccount,
    ServiceRequest,
)
from fieldops.db.session import SessionLocal
from fieldops.intake.schemas import InboundServiceRequest, InboundSource
from fieldops.intake.service import InboundRequestService
from fieldops.observability.metrics import (
    CONVERSATION_SUBMISSIONS_TOTAL,
)
from fieldops.observability.tracing import trace_conversation_operation
from fieldops.schemas.conversation_schemas import (
    ConversationConfirmInput,
    ConversationConfirmResponse,
    ConversationCreateInput,
    ConversationDraftSchema,
    ConversationMessageView,
    ConversationSendMessageInput,
    ConversationSummaryItem,
    ConversationView,
)
from fieldops.security.customer_auth import get_current_customer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customer/conversations", tags=["Customer Conversations"])


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


INITIAL_GREETING = (
    "Hello! I am your FieldOps virtual assistant. "
    "Please describe the maintenance or repair issue you are experiencing, "
    "and I'll help collect the details needed to schedule a technician."
)


def _build_conversation_view(conv: Conversation) -> ConversationView:
    """Helper to convert ORM Conversation to API response schema."""
    draft_dict = conv.draft_snapshot or {}
    draft_schema = ConversationDraftSchema(
        service_type=draft_dict.get("service_type", "General Maintenance"),
        urgency=draft_dict.get("urgency", "medium"),
        location=draft_dict.get("location"),
        preferred_time=draft_dict.get("preferred_time"),
        problem_description=draft_dict.get("problem_description"),
        required_skills=draft_dict.get("required_skills", []),
        missing_fields=draft_dict.get("missing_fields", ["problem_description", "location", "preferred_time"]),
        is_complete=draft_dict.get("is_complete", False),
        safety_warning=draft_dict.get("safety_warning"),
    )

    msg_views: List[ConversationMessageView] = [
        ConversationMessageView(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            client_message_id=m.client_message_id,
            metadata=m.message_metadata,
            created_at=m.created_at.isoformat() if m.created_at else "",
        )
        for m in sorted(conv.messages or [], key=lambda x: x.created_at or datetime.min)
    ]

    return ConversationView(
        id=conv.id,
        customer_id=conv.customer_id,
        status=conv.status,
        draft_version=conv.draft_version,
        draft=draft_schema,
        messages=msg_views,
        submitted_service_request_id=conv.submitted_service_request_id,
        created_at=conv.created_at.isoformat() if conv.created_at else "",
        updated_at=conv.updated_at.isoformat() if conv.updated_at else "",
        last_message_at=conv.last_message_at.isoformat() if conv.last_message_at else None,
    )


# ==============================================================================
# 1. Initialize Conversation
# ==============================================================================


@router.post("", response_model=ConversationView, status_code=status.HTTP_201_CREATED, summary="Create a new intake conversation")
def create_conversation(
    payload: Optional[ConversationCreateInput] = None,
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> ConversationView:
    """Initialize a new conversation session for the authenticated customer."""
    _, customer = auth

    initial_draft = {
        "service_type": "General Maintenance",
        "urgency": "medium",
        "location": None,
        "preferred_time": None,
        "problem_description": None,
        "required_skills": [],
        "missing_fields": ["problem_description", "location", "preferred_time"],
        "is_complete": False,
        "safety_warning": None,
    }

    conv = Conversation(
        customer_id=customer.id,
        status="active",
        draft_snapshot=initial_draft,
        draft_version=1,
    )
    session.add(conv)
    session.flush()

    # Initial greeting
    greeting_msg = ConversationMessage(
        conversation_id=conv.id,
        role="assistant",
        content=INITIAL_GREETING,
        message_metadata={"action": "greeting"},
    )
    session.add(greeting_msg)
    session.flush()

    # Audit
    audit = AuditLog(
        entity_type="conversation",
        entity_id=str(conv.id),
        action="conversation.created",
        details={"customer_id": customer.id},
    )
    session.add(audit)
    session.commit()

    # If initial message supplied, process turn immediately
    if payload and payload.initial_message and payload.initial_message.strip():
        user_text = payload.initial_message.strip()
        user_msg = ConversationMessage(
            conversation_id=conv.id,
            role="customer",
            content=user_text,
            client_message_id=payload.client_message_id,
        )
        session.add(user_msg)
        session.flush()

        updated_draft, next_status, reply, action, warning = process_turn(
            current_draft=conv.draft_snapshot,
            messages=[{"role": "assistant", "content": INITIAL_GREETING}],
            new_message=user_text,
            conversation_id=conv.id,
        )

        conv.draft_snapshot = updated_draft
        conv.draft_version += 1
        conv.status = next_status
        conv.last_message_at = datetime.now(timezone.utc)

        assist_msg = ConversationMessage(
            conversation_id=conv.id,
            role="assistant",
            content=reply,
            message_metadata={"action": action, "warning": warning},
        )
        session.add(assist_msg)
        session.commit()

    session.refresh(conv)
    return _build_conversation_view(conv)


# ==============================================================================
# 2. List Customer Conversations (Anti-IDOR)
# ==============================================================================


@router.get("", response_model=List[ConversationSummaryItem], summary="List conversations for current customer")
def list_conversations(
    status_filter: Optional[str] = Query(None, alias="status"),
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> List[ConversationSummaryItem]:
    """Return all conversations owned by current customer."""
    _, customer = auth
    query = session.query(Conversation).filter_by(customer_id=customer.id)
    if status_filter:
        query = query.filter_by(status=status_filter)

    records = query.order_by(Conversation.updated_at.desc()).all()

    items = []
    for c in records:
        draft = c.draft_snapshot or {}
        preview = draft.get("problem_description") or "New conversation"
        if len(preview) > 60:
            preview = preview[:57] + "..."
        items.append(
            ConversationSummaryItem(
                id=c.id,
                status=c.status,
                service_type=draft.get("service_type"),
                draft_preview=preview,
                submitted_service_request_id=c.submitted_service_request_id,
                created_at=c.created_at.isoformat() if c.created_at else "",
                updated_at=c.updated_at.isoformat() if c.updated_at else "",
            )
        )
    return items


# ==============================================================================
# 3. Get Conversation Detail (Strict Anti-IDOR)
# ==============================================================================


@router.get("/{conversation_id}", response_model=ConversationView, summary="Get conversation detail")
def get_conversation(
    conversation_id: int,
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> ConversationView:
    """Fetch conversation. Returns 404 if unowned or not found."""
    _, customer = auth
    conv = session.query(Conversation).filter_by(id=conversation_id, customer_id=customer.id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation #{conversation_id} not found.",
        )
    return _build_conversation_view(conv)


# ==============================================================================
# 4. Send Message & Run Agent Turn
# ==============================================================================


@router.post("/{conversation_id}/messages", response_model=ConversationView, summary="Send message in conversation")
def send_conversation_message(
    conversation_id: int,
    payload: ConversationSendMessageInput,
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> ConversationView:
    """Send customer message, execute agent parsing, and update draft."""
    _, customer = auth
    conv = session.query(Conversation).filter_by(id=conversation_id, customer_id=customer.id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation #{conversation_id} not found.",
        )

    if conv.status in ("submitted", "cancelled", "closed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Conversation is already {conv.status}. Please start a new conversation.",
        )

    # Message Idempotency / Double-Send Guard
    if payload.client_message_id:
        existing = session.query(ConversationMessage).filter_by(
            conversation_id=conv.id,
            client_message_id=payload.client_message_id,
        ).first()
        if existing:
            logger.info("Message idempotency hit for client_message_id=%s", payload.client_message_id)
            return _build_conversation_view(conv)

    # Save customer message
    cust_msg = ConversationMessage(
        conversation_id=conv.id,
        role="customer",
        content=payload.content.strip(),
        client_message_id=payload.client_message_id,
    )
    session.add(cust_msg)
    session.flush()

    # Load recent context
    history_records = (
        session.query(ConversationMessage)
        .filter_by(conversation_id=conv.id)
        .order_by(ConversationMessage.created_at.asc())
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in history_records[-15:]]

    # Process turn
    updated_draft, next_status, reply, action, warning = process_turn(
        current_draft=conv.draft_snapshot,
        messages=history,
        new_message=payload.content.strip(),
        conversation_id=conv.id,
    )

    conv.draft_snapshot = updated_draft
    conv.draft_version += 1
    conv.status = next_status
    conv.last_message_at = datetime.now(timezone.utc)

    # Save assistant response
    assist_msg = ConversationMessage(
        conversation_id=conv.id,
        role="assistant",
        content=reply,
        message_metadata={"action": action, "warning": warning},
    )
    session.add(assist_msg)

    # Audit
    audit_action = "conversation.message_processed"
    if next_status == "awaiting_confirmation":
        audit_action = "conversation.ready_for_confirmation"

    audit = AuditLog(
        entity_type="conversation",
        entity_id=str(conv.id),
        action=audit_action,
        details={
            "customer_id": customer.id,
            "draft_version": conv.draft_version,
            "status": next_status,
            "is_complete": updated_draft.get("is_complete", False),
        },
    )
    session.add(audit)
    session.commit()
    session.refresh(conv)

    return _build_conversation_view(conv)


# ==============================================================================
# 5. Confirm & Submit Service Request
# ==============================================================================


@router.post("/{conversation_id}/confirm", response_model=ConversationConfirmResponse, summary="Confirm and submit draft as formal ServiceRequest")
def confirm_conversation(
    conversation_id: int,
    payload: Optional[ConversationConfirmInput] = None,
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> ConversationConfirmResponse:
    """Explicitly confirm and submit the draft to existing FieldOps workflow."""
    _, customer = auth
    conv = session.query(Conversation).filter_by(id=conversation_id, customer_id=customer.id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation #{conversation_id} not found.",
        )

    # 1. Double Confirm Idempotency
    if conv.status == "submitted" and conv.submitted_service_request_id:
        logger.info("Conversation #%d already submitted (idempotent replay)", conv.id)
        return ConversationConfirmResponse(
            success=True,
            conversation_id=conv.id,
            service_request_id=conv.submitted_service_request_id,
            status="submitted",
            message=f"Service request #{conv.submitted_service_request_id} has already been submitted.",
        )

    if conv.status != "awaiting_confirmation":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot confirm conversation: not awaiting confirmation (status: '{conv.status}'). Draft must be complete first.",
        )

    draft = conv.draft_snapshot or {}
    missing = draft.get("missing_fields", [])
    if missing or not draft.get("is_complete"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot confirm incomplete draft. Missing: {', '.join(missing)}",
        )

    with trace_conversation_operation("confirm", conversation_id=conv.id):
        # 2. Invoke unified InboundRequestService
        ext_msg_id = f"conv-{conv.id}-{conv.draft_version}"
        intake_msg = (
            f"{draft.get('problem_description', '')}\n"
            f"[Location: {draft.get('location', '')}]\n"
            f"[Preferred Time: {draft.get('preferred_time', '')}]"
        )

        inbound_req = InboundServiceRequest(
            source=InboundSource.CUSTOMER_CONVERSATION,
            external_message_id=ext_msg_id,
            customer_name=customer.name,
            customer_email=customer.email,
            customer_phone=customer.phone,
            message=intake_msg,
            metadata={
                "conversation_id": conv.id,
                "service_type": draft.get("service_type"),
                "urgency": draft.get("urgency", "medium"),
                "location": draft.get("location"),
                "preferred_time": draft.get("preferred_time"),
            },
        )

        intake_service = InboundRequestService()
        inbound_resp = intake_service.handle(inbound_req)

        sr_id = inbound_resp.service_request_id
        if not sr_id:
            # Look up newly created ServiceRequest if not directly returned
            latest_sr = (
                session.query(ServiceRequest)
                .filter_by(customer_id=customer.id)
                .order_by(ServiceRequest.id.desc())
                .first()
            )
            sr_id = latest_sr.id if latest_sr else 0

        # Update ServiceRequest location & preferred_time explicitly if needed
        if sr_id:
            sr = session.query(ServiceRequest).filter_by(id=sr_id).first()
            if sr:
                if draft.get("location"):
                    sr.location = draft["location"]
                if draft.get("service_type"):
                    sr.service_type = draft["service_type"]
                if draft.get("urgency"):
                    sr.urgency = draft["urgency"]
                session.flush()

        # 3. Update Conversation status & pointer
        conv.status = "submitted"
        conv.submitted_service_request_id = sr_id
        conv.last_message_at = datetime.now(timezone.utc)

        # 4. Append confirmation system message
        sys_msg = ConversationMessage(
            conversation_id=conv.id,
            role="system_event",
            content=f"Your Service Request #{sr_id} has been created and submitted to our dispatch team.",
            message_metadata={"service_request_id": sr_id, "action": "confirmed"},
        )
        session.add(sys_msg)

        # 5. Audit Log
        audit = AuditLog(
            entity_type="conversation",
            entity_id=str(conv.id),
            action="conversation.submitted",
            details={
                "customer_id": customer.id,
                "service_request_id": sr_id,
                "external_message_id": ext_msg_id,
            },
        )
        session.add(audit)
        session.commit()

        CONVERSATION_SUBMISSIONS_TOTAL.labels(status="success").inc()

        return ConversationConfirmResponse(
            success=True,
            conversation_id=conv.id,
            service_request_id=sr_id,
            status="submitted",
            message=f"Service request #{sr_id} created successfully.",
        )


# ==============================================================================
# 6. Cancel Conversation
# ==============================================================================


@router.post("/{conversation_id}/cancel", response_model=ConversationView, summary="Cancel active conversation")
def cancel_conversation(
    conversation_id: int,
    auth: tuple[CustomerAccount, Customer] = Depends(get_current_customer),
    session: Session = Depends(get_db),
) -> ConversationView:
    """Cancel an in-flight conversation. If already submitted, ticket must be cancelled via service request flow."""
    _, customer = auth
    conv = session.query(Conversation).filter_by(id=conversation_id, customer_id=customer.id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation #{conversation_id} not found.",
        )

    if conv.status == "submitted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a submitted conversation. Please cancel your service request directly.",
        )

    conv.status = "cancelled"
    conv.last_message_at = datetime.now(timezone.utc)

    sys_msg = ConversationMessage(
        conversation_id=conv.id,
        role="system_event",
        content="This conversation has been cancelled.",
        message_metadata={"action": "cancelled"},
    )
    session.add(sys_msg)

    audit = AuditLog(
        entity_type="conversation",
        entity_id=str(conv.id),
        action="conversation.cancelled",
        details={"customer_id": customer.id},
    )
    session.add(audit)
    session.commit()
    session.refresh(conv)

    return _build_conversation_view(conv)
