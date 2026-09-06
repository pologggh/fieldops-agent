"""Application service managing unified inbound request intake across channels."""

from datetime import datetime, timezone
import logging
from typing import Any
import uuid
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fieldops.application.field_service_workflow import run_field_service_workflow
from fieldops.core.exceptions import ConflictError
from fieldops.core.idempotency import compute_request_hash
from fieldops.db.session import SessionLocal
from fieldops.intake.schemas import InboundResponse, InboundServiceRequest
from fieldops.observability.metrics import (
    INBOUND_DUPLICATES_TOTAL,
    INBOUND_FAILURES_TOTAL,
    INBOUND_REQUESTS_TOTAL,
)
from fieldops.observability.tracing import trace_intake_operation
from fieldops.repositories.audit_log_repository import AuditLogRepository
from fieldops.repositories.inbound_event_repository import InboundEventRepository
from fieldops.repositories.service_request_repository import ServiceRequestRepository

logger = logging.getLogger(__name__)


class InboundRequestService:
    """Coordinates channel-side idempotency, event tracking, and core workflow invocation."""

    def __init__(self, session_factory=None, workflow_runner=None) -> None:
        self.session_factory = session_factory or SessionLocal
        self.workflow_runner = workflow_runner or run_field_service_workflow

    def handle(
        self,
        request: InboundServiceRequest,
        raw_payload: Any = None,
    ) -> InboundResponse:
        """Handle normalized incoming request across any channel."""
        source_val = request.source.value
        ext_msg_id = request.external_message_id

        with trace_intake_operation("normalize", source=source_val, external_message_id=ext_msg_id):
            request_hash = compute_request_hash(raw_payload if raw_payload is not None else request)

        inbound_event_id: int | None = None
        assigned_request_id = str(uuid.uuid4())

        # ======================================================================
        # 1. Source-Level Idempotency Check (for channels providing external_message_id)
        # ======================================================================
        if ext_msg_id:
            with self.session_factory() as session:
                event_repo = InboundEventRepository(session)
                audit_repo = AuditLogRepository(session)
                existing = event_repo.get_by_source_and_external_id(
                    source=source_val, external_message_id=ext_msg_id
                )

                if existing is not None:
                    # 1.1 Hash conflict check: same external_message_id, different payload -> 409
                    if existing.request_hash != request_hash:
                        logger.warning(
                            "Inbound hash mismatch for source=%s msg_id=%s: stored=%s current=%s",
                            source_val,
                            ext_msg_id,
                            existing.request_hash,
                            request_hash,
                        )
                        audit_repo.create(
                            entity_type="inbound_event",
                            entity_id=str(existing.id),
                            action="inbound.duplicate",
                            details={"source": source_val, "conflict": True},
                        )
                        session.commit()
                        INBOUND_REQUESTS_TOTAL.labels(source=source_val, result="conflict").inc()
                        raise ConflictError(
                            f"Inbound conflict: payload does not match original request for {ext_msg_id}."
                        )

                    # 1.2 Completed duplicate -> return cached/reconstructed result
                    if existing.status == "completed":
                        logger.info(
                            "Inbound duplicate hit (completed) for source=%s msg_id=%s",
                            source_val,
                            ext_msg_id,
                        )
                        audit_repo.create(
                            entity_type="inbound_event",
                            entity_id=str(existing.id),
                            action="inbound.duplicate",
                            details={"source": source_val, "status": "completed"},
                        )
                        session.commit()
                        INBOUND_DUPLICATES_TOTAL.labels(source=source_val).inc()
                        INBOUND_REQUESTS_TOTAL.labels(source=source_val, result="duplicate").inc()

                        wf_status = "completed"
                        if existing.service_request_id:
                            sr_repo = ServiceRequestRepository(session)
                            sr = sr_repo.get_by_id(existing.service_request_id)
                            if sr:
                                wf_status = sr.status

                        return InboundResponse(
                            request_id=existing.request_id or "",
                            service_request_id=existing.service_request_id,
                            workflow_status=wf_status,
                            source=existing.source,
                            duplicate=True,
                            details={"message": "Duplicate request acknowledged.", "external_message_id": ext_msg_id},
                        )

                    # 1.3 In flight processing -> 409
                    if existing.status == "processing":
                        logger.warning(
                            "Inbound concurrent conflict (in flight) for source=%s msg_id=%s",
                            source_val,
                            ext_msg_id,
                        )
                        INBOUND_REQUESTS_TOTAL.labels(source=source_val, result="conflict").inc()
                        raise ConflictError(
                            f"A request with external_message_id '{ext_msg_id}' is currently being processed."
                        )

                    # 1.4 Failed earlier: allow retry by updating status back to processing
                    existing.status = "processing"
                    existing.updated_at = datetime.now(timezone.utc)
                    session.commit()
                    inbound_event_id = existing.id
                    if existing.request_id:
                        assigned_request_id = existing.request_id

        # ======================================================================
        # 2. Initial InboundEvent Recording (Short Transaction Boundary)
        # ======================================================================
        if inbound_event_id is None:
            with self.session_factory() as session:
                event_repo = InboundEventRepository(session)
                audit_repo = AuditLogRepository(session)
                try:
                    event = event_repo.create(
                        source=source_val,
                        external_message_id=ext_msg_id,
                        request_hash=request_hash,
                        status="received",
                        request_id=assigned_request_id,
                    )
                    session.commit()
                    inbound_event_id = event.id

                    audit_repo.create(
                        entity_type="inbound_event",
                        entity_id=str(inbound_event_id),
                        action="inbound.received",
                        details={"source": source_val, "external_message_id": ext_msg_id},
                    )
                    session.commit()

                    # Transition to processing
                    event_repo.mark_processing(inbound_event_id, request_id=assigned_request_id)
                    session.commit()

                except IntegrityError:
                    session.rollback()
                    INBOUND_REQUESTS_TOTAL.labels(source=source_val, result="conflict").inc()
                    raise ConflictError(
                        f"Concurrent request with external_message_id '{ext_msg_id}' is being processed."
                    )

        # ======================================================================
        # 3. Execute Core LangGraph Workflow (Outside DB Transaction)
        # ======================================================================
        try:
            with trace_intake_operation("process", source=source_val, external_message_id=ext_msg_id):
                final_state = self.workflow_runner(
                    message=request.message,
                    customer_name=request.customer_name,
                    email=request.customer_email or "",
                    phone=request.customer_phone,
                    request_id=assigned_request_id,
                    source=source_val,
                    inbound_event_id=inbound_event_id,
                )

            wf_status = final_state.get("workflow_status") or "completed"
            sr_id = final_state.get("service_request_id")
            err_code = final_state.get("error_code")

            # Check if workflow reached a terminal failure state
            is_workflow_failure = wf_status in ("parse_failed", "validation_failed", "llm_failed", "error")

            # ==================================================================
            # 4. Update InboundEvent Status
            # ==================================================================
            with self.session_factory() as session:
                event_repo = InboundEventRepository(session)
                audit_repo = AuditLogRepository(session)

                if is_workflow_failure:
                    err_summary = final_state.get("error_message") or f"Workflow failed with status: {wf_status}"
                    if inbound_event_id:
                        event_repo.mark_failed(inbound_event_id, error_summary=err_summary)
                    audit_repo.create(
                        entity_type="inbound_event",
                        entity_id=str(inbound_event_id or 0),
                        action="inbound.failed",
                        details={"source": source_val, "error_code": err_code, "workflow_status": wf_status},
                    )
                    session.commit()

                    INBOUND_FAILURES_TOTAL.labels(source=source_val).inc()
                    INBOUND_REQUESTS_TOTAL.labels(source=source_val, result="failed").inc()
                else:
                    if inbound_event_id:
                        event_repo.mark_completed(
                            inbound_event_id,
                            request_id=assigned_request_id,
                            service_request_id=sr_id,
                        )
                    audit_repo.create(
                        entity_type="inbound_event",
                        entity_id=str(inbound_event_id or 0),
                        action="inbound.completed",
                        details={"source": source_val, "service_request_id": sr_id, "workflow_status": wf_status},
                    )
                    session.commit()

                    INBOUND_REQUESTS_TOTAL.labels(source=source_val, result="success").inc()

            return InboundResponse(
                request_id=assigned_request_id,
                service_request_id=sr_id,
                workflow_status=wf_status,
                source=source_val,
                duplicate=False,
                details={
                    "customer_name": request.customer_name,
                    "service_type": final_state.get("service_type"),
                    "urgency": final_state.get("urgency"),
                    "location": final_state.get("location"),
                    "appointment_proposal": final_state.get("appointment_proposal"),
                    "raw_state": final_state,
                },
            )

        except Exception as exc:
            logger.error("Inbound workflow processing error for source=%s: %s", source_val, exc)
            with self.session_factory() as session:
                if inbound_event_id:
                    event_repo = InboundEventRepository(session)
                    event_repo.mark_failed(inbound_event_id, error_summary=str(exc))
                audit_repo = AuditLogRepository(session)
                audit_repo.create(
                    entity_type="inbound_event",
                    entity_id=str(inbound_event_id or 0),
                    action="inbound.failed",
                    details={"source": source_val, "error": str(exc)},
                )
                session.commit()

            INBOUND_FAILURES_TOTAL.labels(source=source_val).inc()
            INBOUND_REQUESTS_TOTAL.labels(source=source_val, result="failed").inc()
            raise
