"""FastAPI main application for FieldOps Agent with Reliability Engineering."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from pathlib import Path
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import jwt
import redis
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import and_, desc, or_, text
from sqlalchemy.exc import DatabaseError, IntegrityError, SQLAlchemyError

from fieldops.security.admin_auth import (
    get_current_admin,
    get_current_internal_reader,
    get_current_internal_user,
    get_current_operator_or_admin,
)
from fieldops.security.rate_limiter import rate_limiter

from fieldops.application import (
    WorkflowAlreadyCompletedError,
    WorkflowNotFoundError,
    resume_field_service_workflow,
    run_field_service_workflow,
)
from fieldops.application.appointment_service import AppointmentService
from fieldops.core.config import settings
from fieldops.core.exceptions import (
    ConflictError,
    DatabaseOperationError,
    DuplicateRequestError,
    FieldOpsError,
    LLMServiceError,
    LLMTimeoutError,
    ResourceNotFoundError,
    ValidationError,
    WorkflowStateError,
)
from fieldops.core.idempotency import compute_request_hash
from fieldops.core.logging import log_operation, redact_email, sanitize_message
from fieldops.core.middleware import CorrelationIdMiddleware
from fieldops.db.models import (
    Appointment,
    AuditLog,
    InternalUser,
    OutboxEvent,
    ServiceRequest,
    Technician,
)
from fieldops.db.session import SessionLocal
from fieldops.llm import (
    AnalyzeServiceRequestResponse,
    EmptyMessageError,
    LLMCallError,
    LLMConfigurationError,
    ParsedServiceRequest,
    ParseRequestInput,
    ServiceRequestApprovalInput,
    ServiceRequestApprovalResponse,
    ServiceRequestCreateInput,
    ServiceRequestCreateResponse,
    parse_service_request,
)
from fieldops.observability.metrics import get_metrics_response
from fieldops.observability.tracing import setup_tracing
from fieldops.repositories.appointment_repository import AppointmentRepository
from fieldops.repositories.idempotency_repository import IdempotencyRepository
from fieldops.repositories.integration_repository import IntegrationRepository
from fieldops.intake import (
    FakeEmailInboundAdapter,
    FakeEmailPayload,
    InboundRequestService,
    InboundResponse,
    WebInboundAdapter,
    WebhookInboundAdapter,
    WebhookPayload,
)
from fieldops.repositories.notification_job_repository import (
    NotificationJobRepository,
)

from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)



class InternalTokenBoundaryMiddleware(BaseHTTPMiddleware):
    """Enforces strict token boundary: Customer tokens cannot access internal operator endpoints."""
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Allow customer portal endpoints, customer auth, and documentation/system endpoints
        if not path.startswith("/customer") and not path.startswith("/customer-auth"):
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "").strip()
                try:
                    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
                    if payload.get("type") == "customer" or payload.get("account_type") == "customer":
                        return JSONResponse(
                            status_code=403,
                            content={"detail": "Customer tokens cannot access internal operator endpoints."},
                        )
                except Exception:
                    pass
        return await call_next(request)


app = FastAPI(
    title="FieldOps Agent API",
    description="Field Service Operations AI Agent with Reliability Engineering",
    version="0.1.0",
)

setup_tracing(app)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(InternalTokenBoundaryMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Global Exception Handlers (HTTP Error Mapping)
# ==============================================================================


@app.exception_handler(FieldOpsError)
def handle_fieldops_error(request: Request, exc: FieldOpsError) -> JSONResponse:
    """Map domain FieldOpsErrors to appropriate HTTP status codes and structured payload."""
    logger.warning(
        "FieldOpsError handled: status_code=%d, type=%s, retryable=%s, message=%s",
        exc.status_code,
        type(exc).__name__,
        exc.retryable,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "error_type": type(exc).__name__,
            "retryable": exc.retryable,
        },
    )


DASHBOARD_HTML_PATH = Path(__file__).resolve().parent / "templates" / "dashboard.html"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard_endpoint() -> HTMLResponse:
    """Serve the interactive web frontend dashboard."""
    if DASHBOARD_HTML_PATH.exists():
        return HTMLResponse(content=DASHBOARD_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>FieldOps Agent API</h1><p>Visit <a href='/docs'>/docs</a> for Swagger UI.</p>")


@app.get("/technicians", status_code=status.HTTP_200_OK, summary="List all technicians")
def list_technicians_endpoint(
    user: InternalUser = Depends(get_current_internal_reader),
) -> list[dict[str, Any]]:
    """List all registered technicians and their skill specializations."""
    with SessionLocal() as session:
        from fieldops.db.models import Technician
        techs = session.query(Technician).all()
        return [
            {
                "id": t.id,
                "name": t.name,
                "service_area": t.service_area,
                "status": t.status,
                "skills": [s.skill for s in t.skills] if hasattr(t, "skills") else [],
            }
            for t in techs
        ]


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint (Liveness probe)."""
    return {"status": "ok"}


@app.get("/ready")
def readiness(response: Response) -> dict[str, Any]:
    """Readiness probe checking database and redis dependencies.

    - PostgreSQL is critical: if DB check fails, returns 503 Service Unavailable.
    - Redis is degraded: if Redis check fails, returns 200 OK with degraded status,
      because Transactional Outbox ensures appointments can still be scheduled.
    """
    db_status = "ok"
    redis_status = "ok"

    # 1. PostgreSQL check (Critical)
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("Readiness check failed for PostgreSQL: %s", e)
        db_status = "error"

    # 2. Redis check (Degraded)
    try:
        r = redis.from_url(settings.REDIS_URL, socket_timeout=1.0)
        r.ping()
    except Exception as e:
        logger.warning("Readiness check: Redis degraded: %s", e)
        redis_status = "degraded"

    if db_status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "database": db_status,
            "redis": redis_status,
        }

    overall_status = "ok" if redis_status == "ok" else "degraded"
    return {
        "status": overall_status,
        "database": db_status,
        "redis": redis_status,
    }


@app.get("/metrics")
def metrics() -> Response:
    """Expose Prometheus metrics for scraping."""
    return get_metrics_response()


class LoginInput(BaseModel):
    username: str
    password: str


@app.post(
    "/auth/login",
    status_code=status.HTTP_200_OK,
    summary="User login with rate limit defense against brute-force attacks",
)
def login_endpoint(
    payload: LoginInput,
    request: Request,
) -> dict[str, Any]:
    """Authenticate operator with rate limiting against real database records."""
    rate_limiter(
        max_requests=settings.RATE_LIMIT_LOGIN_MAX_REQUESTS,
        window_seconds=settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS,
        is_auth=True,
    )(request)

    from fieldops.db.models import InternalUser
    from fieldops.security.admin_auth import verify_password, create_access_token
    with SessionLocal() as session:
        user_in_db = session.query(InternalUser).filter(
            or_(InternalUser.email == payload.username, InternalUser.email == f"{payload.username}@fieldops.com")
        ).first()
        if not user_in_db:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials.",
            )
        if not user_in_db.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account has been deactivated. Please contact your system administrator.",
            )
        if not verify_password(payload.password, user_in_db.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials.",
            )

        user_in_db.last_login = datetime.now(timezone.utc)
        session.commit()
        token = create_access_token({
            "sub": str(user_in_db.id),
            "user_id": user_in_db.id,
            "email": user_in_db.email,
            "role": user_in_db.role,
            "type": "access",
        })
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "email": user_in_db.email,
                "name": user_in_db.name,
                "role": user_in_db.role,
            },
        }


@app.get("/auth/me", summary="Get current logged in user information")
def get_current_user(
    user: InternalUser = Depends(get_current_internal_user),
) -> dict[str, Any]:
    """Return user profile from verified Bearer token."""
    return {
        "email": user.email,
        "name": user.name,
        "role": user.role,
    }



@app.post(
    "/parse-service-request",
    response_model=ParsedServiceRequest,
    status_code=status.HTTP_200_OK,
    summary="Parse raw customer service request into structured format",
)
def parse_request(payload: ParseRequestInput) -> ParsedServiceRequest:
    """Parse raw natural language customer message into structured fields."""
    try:
        return parse_service_request(payload.message)
    except EmptyMessageError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except LLMConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    except LLMTimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    except LLMCallError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("Unexpected parsing error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while parsing the service request.",
        ) from e


@app.post(
    "/service-requests/analyze",
    response_model=AnalyzeServiceRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze customer service request through LangGraph workflow",
)
def analyze_service_request(
    payload: ParseRequestInput,
) -> AnalyzeServiceRequestResponse:
    """Execute LangGraph workflow pipeline to parse and validate service request."""
    try:
        result_state = run_field_service_workflow(message=payload.message)
        return AnalyzeServiceRequestResponse(**result_state)
    except EmptyMessageError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except (LLMConfigurationError, LLMTimeoutError, LLMCallError) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("Unexpected workflow analysis error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during service request analysis.",
        ) from e


@app.post(
    "/service-requests",
    response_model=ServiceRequestCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer service request with idempotency, validation, and persistence",
)
def create_service_request(
    payload: ServiceRequestCreateInput,
    response: Response,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user: InternalUser = Depends(get_current_operator_or_admin),
) -> ServiceRequestCreateResponse:
    """Execute full intake workflow with robust idempotency and error classification."""
    # 0. Request size validation and rate limiting (Phase 18 Hardening)
    if len(payload.message) > settings.MAX_REQUEST_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Request message exceeds maximum allowed length of {settings.MAX_REQUEST_MESSAGE_LENGTH} characters.",
        )

    rate_limiter(
        max_requests=settings.RATE_LIMIT_SERVICE_REQUEST_MAX_REQUESTS,
        window_seconds=settings.RATE_LIMIT_SERVICE_REQUEST_WINDOW_SECONDS,
        is_auth=False,
    )(request)

    operation_name = "create_service_request"
    current_hash = compute_request_hash(payload)

    # 1. Idempotency verification if header provided
    if idempotency_key:
        with SessionLocal() as session:
            idempotency_repo = IdempotencyRepository(session)
            record = idempotency_repo.get(idempotency_key, operation_name)

            if record is not None:
                # Hash mismatch check: same key but different body -> 409 Conflict
                if record.request_hash != current_hash:
                    logger.warning(
                        "Idempotency hash mismatch for key=%s: stored=%s, current=%s",
                        idempotency_key,
                        record.request_hash,
                        current_hash,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Idempotency key conflict: request payload does not match original request.",
                    )

                # Completed check: return cached previous response
                if record.status == "completed" and record.response_payload:
                    logger.info("Idempotency hit (completed) for key=%s. Returning cached response.", idempotency_key)
                    return ServiceRequestCreateResponse(**record.response_payload)

                # Processing check: concurrent request in flight -> 409 Conflict
                if record.status == "processing":
                    logger.warning("Idempotency conflict (in flight) for key=%s", idempotency_key)
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="A request with this Idempotency-Key is currently being processed.",
                    )

                # If failed earlier, allow retry
                record.status = "processing"
                session.commit()
            else:
                # Insert initial processing record
                try:
                    idempotency_repo.create(
                        key=idempotency_key,
                        operation=operation_name,
                        request_hash=current_hash,
                        status="processing",
                    )
                    session.commit()
                except (IntegrityError, DatabaseError):
                    session.rollback()
                    # Concurrent request just inserted this key
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Concurrent request with this Idempotency-Key is currently being processed.",
                    )

    # 2. Execute business workflow
    try:
        with log_operation(
            "create_service_request",
            extra_context={
                "idempotency_key": idempotency_key,
                "email": redact_email(payload.email),
                "message": sanitize_message(payload.message),
            },
        ) as log_ctx:
            inbound_req = WebInboundAdapter.normalize(payload)
            inbound_service = InboundRequestService(workflow_runner=run_field_service_workflow)
            inbound_res = inbound_service.handle(inbound_req, raw_payload=payload)
            final_state = (inbound_res.details.get("raw_state", {}) if inbound_res.details else {})
            log_ctx["service_request_id"] = final_state.get("service_request_id")
            log_ctx["workflow_status"] = final_state.get("workflow_status")

        # 3. Save successful response payload in idempotency record
        if idempotency_key:
            with SessionLocal() as session:
                idempotency_repo = IdempotencyRepository(session)
                idempotency_repo.mark_completed(
                    key=idempotency_key,
                    operation=operation_name,
                    response_payload=final_state,
                    resource_id=final_state.get("service_request_id"),
                )
                session.commit()

        return ServiceRequestCreateResponse(**final_state)

    except EmptyMessageError as e:
        if idempotency_key:
            _mark_idempotency_failed(idempotency_key, operation_name)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except (LLMConfigurationError, LLMTimeoutError, LLMCallError) as e:
        if idempotency_key:
            _mark_idempotency_failed(idempotency_key, operation_name)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    except IntegrityError as e:
        if idempotency_key:
            _mark_idempotency_failed(idempotency_key, operation_name)
        logger.error("Database integrity error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity constraint violated.",
        ) from e
    except SQLAlchemyError as e:
        if idempotency_key:
            _mark_idempotency_failed(idempotency_key, operation_name)
        logger.error("Database operational error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed. Please try again later.",
        ) from e
    except Exception as e:
        if idempotency_key:
            _mark_idempotency_failed(idempotency_key, operation_name)
        logger.error("Unexpected service request creation error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the service request.",
        ) from e


def _mark_idempotency_failed(key: str, operation: str) -> None:
    try:
        with SessionLocal() as session:
            idempotency_repo = IdempotencyRepository(session)
            idempotency_repo.mark_failed(key, operation)
            session.commit()
    except Exception as e:
        logger.error("Failed to mark idempotency record as failed: %s", e)


@app.post(
    "/service-requests/{request_id}/approval",
    response_model=ServiceRequestApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Operator approval decision for an appointment proposal",
)
def approve_service_request(
    request_id: str,
    payload: ServiceRequestApprovalInput,
    user: InternalUser = Depends(get_current_operator_or_admin),
) -> ServiceRequestApprovalResponse:
    """Submit an operator decision ('approve' or 'reject') to resume an interrupted workflow."""
    try:
        with log_operation(
            "approve_service_request",
            request_id=request_id,
            extra_context={"decision": payload.decision},
        ):
            try:
                updated_state = resume_field_service_workflow(
                    request_id=request_id,
                    decision=payload.decision,
                    reason=payload.reason,
                    actor_role=user.role,
                )
                return ServiceRequestApprovalResponse(**updated_state)
            except WorkflowNotFoundError as e:
                # Check if request_id matches a DB ServiceRequest
                with SessionLocal() as session:
                    from fieldops.db.models import ServiceRequest, Appointment, AuditLog, OutboxEvent
                    sr = None
                    try:
                        sr = session.query(ServiceRequest).filter_by(id=int(request_id)).first()
                    except (ValueError, TypeError):
                        pass

                    if not sr:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(e),
                        )

                    if sr.status not in [
                        "created",
                        "received",
                        "pending",
                        "waiting_for_approval",
                        "ready_for_review",
                        "needs_rescheduling",
                        "no_technician_available",
                        "escalated",
                    ]:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Service request #{sr.id} is already in '{sr.status}' status and cannot be approved or rejected.",
                        )

                    if payload.decision == "reject":
                        sr.status = "rejected"
                        audit = AuditLog(
                            entity_type="service_request",
                            entity_id=str(sr.id),
                            action="approval.rejected",
                            details={
                                "summary": f"Proposal rejected by operator: {payload.reason or 'No reason specified'}",
                                "actor": "Operator",
                            },
                        )
                        session.add(audit)
                        session.commit()
                        return ServiceRequestApprovalResponse(
                            request_id=request_id,
                            service_request_id=sr.id,
                            workflow_status="rejected",
                            approval_status="rejected",
                            approval_reason=payload.reason,
                        )

                    # Approve: check dispatch rankings
                    rankings = _compute_dispatch_rankings(session, sr)
                    if not rankings:
                        sr.status = "conflict"
                        session.commit()
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="The proposed appointment is no longer available and requires rescheduling.",
                        )

                    top_tech = rankings[0]
                    now_utc = datetime.now(timezone.utc)
                    start_dt = (now_utc + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
                    end_dt = start_dt + timedelta(hours=2)

                    # Check for slot conflicts
                    conflict = session.query(Appointment).filter(
                        Appointment.technician_id == top_tech["technician_id"],
                        Appointment.service_request_id != sr.id,
                        Appointment.status.notin_(["cancelled", "completed"]),
                        Appointment.start_time < end_dt,
                        Appointment.end_time > start_dt,
                    ).first()

                    if conflict:
                        sr.status = "conflict"
                        session.commit()
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="The proposed appointment is no longer available and requires rescheduling.",
                        )

                    # Supersede any prior appointments for this service request (preserving historical records)
                    prior_appts = session.query(Appointment).filter(
                        Appointment.service_request_id == sr.id,
                        Appointment.status.notin_(["cancelled", "completed"])
                    ).all()
                    for prior in prior_appts:
                        prior.status = "cancelled"
                        session.add(
                            OutboxEvent(
                                event_type="appointment.cancelled",
                                aggregate_type="appointment",
                                aggregate_id=str(prior.id),
                                payload={"appointment_id": prior.id, "reason": "Superseded by reschedule"},
                            )
                        )

                    appt = Appointment(
                        service_request_id=sr.id,
                        technician_id=top_tech["technician_id"],
                        start_time=start_dt,
                        end_time=end_dt,
                        status="scheduled",
                    )
                    session.add(appt)
                    sr.status = "scheduled"
                    if "policy_version" in top_tech:
                        sr.dispatch_policy_version = top_tech["policy_version"]
                    session.flush()

                    audit = AuditLog(
                        entity_type="appointment",
                        entity_id=str(appt.id),
                        action="appointment.created",
                        details={
                            "summary": f"Appointment confirmed with {top_tech['name']} ({start_dt.strftime('%Y-%m-%d %H:%M UTC')})",
                            "actor": "Operator",
                        },
                    )
                    session.add(audit)

                    # Enqueue Outbox event for appointment.created so Celery / Notification worker triggers async notifications
                    outbox = OutboxEvent(
                        event_type="appointment.created",
                        aggregate_type="appointment",
                        aggregate_id=str(appt.id),
                        payload={
                            "appointment_id": appt.id,
                            "service_request_id": sr.id,
                            "customer_id": sr.customer_id,
                            "technician_id": top_tech["technician_id"],
                            "start_time": start_dt.isoformat(),
                            "end_time": end_dt.isoformat(),
                        },
                    )
                    session.add(outbox)
                    session.commit()

                    return ServiceRequestApprovalResponse(
                        request_id=request_id,
                        service_request_id=sr.id,
                        workflow_status="completed",
                        approval_status="approved",
                        appointment_id=appt.id,
                        appointment_status="scheduled",
                    )
    except HTTPException:
        raise
    except WorkflowAlreadyCompletedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except WorkflowStateError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("Unexpected error during approval processing: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the approval decision.",
        ) from e


@app.get(
    "/internal/workflows/{request_id}",
    summary="Runtime inspection of workflow execution state for internal operators",
    tags=["Workflow"],
)
def inspect_workflow(
    request_id: str,
    user: InternalUser = Depends(get_current_operator_or_admin),
):
    """Retrieve structured execution state snapshot without exposing prompts or credentials."""
    from fieldops.agent.graph import field_service_graph

    config = {"configurable": {"thread_id": request_id}}
    snapshot = field_service_graph.get_state(config)
    if not snapshot or not snapshot.values:
        # Check database service request as fallback
        with SessionLocal() as session:
            sr = None
            try:
                sr = session.query(ServiceRequest).filter_by(id=int(request_id)).first()
            except (ValueError, TypeError):
                pass
            if not sr:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workflow thread '{request_id}' not found in active checkpoints or database.",
                )
            return {
                "request_id": request_id,
                "service_request_id": sr.id,
                "workflow_status": sr.status,
                "current_subgraph": None,
                "human_review_level": "none",
                "step_count": 0,
                "clarification_count": 0,
                "reschedule_count": 0,
                "retry_count": 0,
                "last_decision": None,
                "decision_history": [],
                "integration_status": None,
                "error_summary": None,
            }

    vals = snapshot.values
    return {
        "request_id": vals.get("request_id", request_id),
        "service_request_id": vals.get("service_request_id"),
        "workflow_status": vals.get("workflow_status", "unknown"),
        "current_subgraph": vals.get("current_subgraph"),
        "human_review_level": vals.get("human_review_level", "none"),
        "step_count": vals.get("step_count", 0),
        "clarification_count": vals.get("clarification_count", 0),
        "reschedule_count": vals.get("reschedule_count", 0),
        "retry_count": vals.get("retry_count", 0),
        "last_decision": vals.get("last_decision"),
        "decision_history": vals.get("decision_history", []),
        "integration_status": vals.get("integration_status"),
        "error_summary": {
            "error_code": vals.get("error_code"),
            "error_message": vals.get("error_message"),
            "failed_step": vals.get("failed_step"),
            "retryable": vals.get("retryable", False),
        } if vals.get("error_code") else None,
    }


# ==============================================================================
# Operator Dashboard API Complements (Phase 21)
# ==============================================================================


def _compute_sla_info(sr: ServiceRequest, session: Any = None) -> dict[str, Any]:
    from fieldops.db.models import SLAPolicy
    now = datetime.now(timezone.utc)
    created = sr.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    # If already set on SR, use saved deadline
    if sr.sla_deadline:
        resolution_deadline = sr.sla_deadline
        if resolution_deadline.tzinfo is None:
            resolution_deadline = resolution_deadline.replace(tzinfo=timezone.utc)
        response_deadline = created + (resolution_deadline - created) / 4
        resp_h = int((response_deadline - created).total_seconds() / 3600)
        res_h = int((resolution_deadline - created).total_seconds() / 3600)
    else:
        active_sla = None
        if session:
            try:
                active_sla = session.query(SLAPolicy).filter_by(is_active=True).first()
            except Exception:
                pass

        if active_sla and active_sla.targets:
            urgency_map = {"emergency": "P0", "high": "P1", "medium": "P2", "low": "P3"}
            tier = urgency_map.get((sr.urgency or "medium").lower(), "P2")
            tier_targets = active_sla.targets.get(tier, {})
            resp_mins = tier_targets.get("response_minutes", 240)
            res_mins = tier_targets.get("service_start_minutes", 1440)
            resp_h = resp_mins / 60.0
            res_h = res_mins / 60.0
        else:
            urgency_hours = {
                "emergency": (1, 4),
                "high": (2, 8),
                "medium": (4, 24),
                "low": (8, 48),
            }
            resp_h, res_h = urgency_hours.get((sr.urgency or "medium").lower(), (4, 24))

        response_deadline = created + timedelta(hours=resp_h)
        resolution_deadline = created + timedelta(hours=res_h)

    if sr.status in ["scheduled", "completed"]:
        sla_status = "completed"
    elif now > resolution_deadline:
        sla_status = "breached"
    elif now > response_deadline:
        sla_status = "at_risk"
    else:
        sla_status = "on_track"

    return {
        "sla_status": sla_status,
        "response_deadline": response_deadline.isoformat(),
        "resolution_deadline": resolution_deadline.isoformat(),
        "response_hours": resp_h,
        "resolution_hours": res_h,
        "policy_version": sr.sla_policy_version,
    }


def _compute_dispatch_rankings(session, sr: ServiceRequest) -> list[dict[str, Any]]:
    from fieldops.db.models import Technician, Appointment, DispatchPolicy
    # Only active technicians are eligible for dispatch
    technicians = session.query(Technician).filter(Technician.status == "active").all()
    candidates = []

    req_skills = [sr.service_type.lower()] if sr.service_type else []

    active_policy = None
    try:
        active_policy = session.query(DispatchPolicy).filter_by(is_active=True).first()
    except Exception:
        pass

    policy_ver = active_policy.version if active_policy else 1
    policy_weights = active_policy.weights if active_policy else {}

    workload_w = float(policy_weights.get("workload_weight", 20))
    capacity_w = float(policy_weights.get("capacity_weight", 20))
    sla_w = float(policy_weights.get("sla_weight", 40))
    travel_w = float(policy_weights.get("travel_weight", 10))
    overtime_pen = float(policy_weights.get("overtime_penalty", 10))

    for tech in technicians:
        score = 20.0
        reasons = []

        tech_skills = [s.skill.lower() for s in tech.skills]
        has_skill = any(s in tech_skills for s in req_skills)
        if has_skill:
            score += sla_w
            reasons.append(f"Primary skill matched: {sr.service_type} (+{int(sla_w)} pts)")
        else:
            score += (sla_w * 0.3)
            reasons.append(f"Secondary cross-training available ({', '.join([s.skill for s in tech.skills])})")

        if tech.service_area.lower() == (sr.location or "").lower():
            score += travel_w
            reasons.append(f"Operating in target district: {sr.location} (+{int(travel_w)} pts)")
        else:
            score += (travel_w * 0.2)
            reasons.append(f"Adjacent service area: {tech.service_area}")

        active_appts = session.query(Appointment).filter(
            Appointment.technician_id == tech.id,
            Appointment.status == "scheduled"
        ).count()
        if active_appts == 0:
            score += workload_w
            reasons.append(f"Optimal capacity: 0 scheduled jobs today (+{int(workload_w)} pts)")
        else:
            score += max(0.0, workload_w - active_appts * 5.0)
            reasons.append(f"Moderate workload: {active_appts} existing job(s)")

        max_jobs = tech.max_daily_jobs or 5
        if active_appts < max_jobs:
            score += capacity_w
            reasons.append(f"Within daily capacity ({active_appts}/{max_jobs}) (+{int(capacity_w)} pts)")
        else:
            score -= overtime_pen
            reasons.append(f"Overtime threshold exceeded (-{int(overtime_pen)} pts)")

        final_score = int(min(100.0, max(10.0, score)))
        candidates.append({
            "technician_id": tech.id,
            "name": tech.name,
            "service_area": tech.service_area,
            "skills": [s.skill for s in tech.skills],
            "score": final_score,
            "availability": "available" if active_appts < 3 else "busy",
            "workload": active_appts,
            "capacity": "high" if active_appts == 0 else "medium",
            "sla_fit": "high" if final_score >= 70 else "medium",
            "travel_estimate": "15-25 mins" if tech.service_area.lower() == (sr.location or "").lower() else "35-50 mins",
            "reasons": reasons,
            "policy_version": policy_ver,
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    for idx, c in enumerate(candidates, start=1):
        c["rank"] = idx
    return candidates


@app.get("/dashboard/summary", summary="Get operational dashboard metrics summary")
def get_dashboard_summary(
    user: InternalUser = Depends(get_current_internal_reader),
) -> dict[str, Any]:
    """Return aggregated operational counters for dashboard overview."""
    with SessionLocal() as session:
        from fieldops.db.models import ServiceRequest, Appointment, OutboxEvent
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        open_sr = session.query(ServiceRequest).filter(ServiceRequest.status.notin_(["completed", "cancelled"])).count()
        waiting_approval = session.query(ServiceRequest).filter(
            ServiceRequest.status.in_(["waiting_for_approval", "ready_for_review"])
        ).count()
        today_appts = session.query(Appointment).filter(
            Appointment.start_time >= start_of_day, Appointment.start_time < end_of_day
        ).count()
        total_appts = session.query(Appointment).count()

        escalations = session.query(ServiceRequest).filter(
            or_(
                ServiceRequest.urgency.in_(["high", "emergency"]),
                ServiceRequest.status.in_(["needs_rescheduling", "conflict", "no_technician"])
            ),
            ServiceRequest.status.notin_(["completed", "cancelled"])
        ).count()

        two_hours_ago = now - timedelta(hours=2)
        four_hours_ago = now - timedelta(hours=4)
        sla_at_risk = session.query(ServiceRequest).filter(
            ServiceRequest.created_at <= two_hours_ago,
            ServiceRequest.created_at > four_hours_ago,
            ServiceRequest.status.notin_(["completed", "scheduled", "cancelled"])
        ).count()
        sla_breached = session.query(ServiceRequest).filter(
            ServiceRequest.created_at <= four_hours_ago,
            ServiceRequest.status.notin_(["completed", "scheduled", "cancelled"])
        ).count()

        pending_outbox = session.query(OutboxEvent).filter_by(status="pending").count()

        return {
            "open_service_requests": open_sr,
            "waiting_approval_count": waiting_approval,
            "today_appointments_count": today_appts,
            "total_appointments_count": total_appts,
            "open_escalations_count": escalations,
            "sla_at_risk_count": sla_at_risk,
            "sla_breached_count": sla_breached,
            "pending_outbox_count": pending_outbox,
        }


@app.get("/service-requests", summary="List service requests with filters")
def list_service_requests_endpoint(
    status: str | None = None,
    urgency: str | None = None,
    page: int = 1,
    limit: int = 50,
    user: InternalUser = Depends(get_current_internal_reader),
) -> dict[str, Any]:
    """List service requests with customer details and SLA status."""
    with SessionLocal() as session:
        from fieldops.db.models import ServiceRequest
        query = session.query(ServiceRequest)
        if status:
            query = query.filter(ServiceRequest.status == status)
        if urgency:
            query = query.filter(ServiceRequest.urgency == urgency)

        total = query.count()
        records = query.order_by(desc(ServiceRequest.created_at)).offset((page - 1) * limit).limit(limit).all()

        items = []
        for sr in records:
            sla = _compute_sla_info(sr)
            items.append({
                "id": sr.id,
                "customer_id": sr.customer_id,
                "customer_name": sr.customer.name if sr.customer else "Unknown",
                "customer_email": sr.customer.email if sr.customer else "",
                "customer_phone": sr.customer.phone if sr.customer else "",
                "raw_message": sr.raw_message,
                "service_type": sr.service_type,
                "urgency": sr.urgency,
                "location": sr.location,
                "status": sr.status,
                "created_at": sr.created_at.isoformat(),
                "sla_status": sla["sla_status"],
                "sla_deadline": sla["resolution_deadline"],
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
        }


@app.get("/service-requests/{id}", summary="Get detailed service request")
def get_service_request_endpoint(
    id: int,
    user: InternalUser = Depends(get_current_internal_reader),
) -> dict[str, Any]:
    """Fetch complete service request detail, dispatch rankings, proposal, and audit timeline."""
    with SessionLocal() as session:
        from fieldops.db.models import ServiceRequest, AuditLog, Appointment, Technician
        sr = session.query(ServiceRequest).filter_by(id=id).first()
        if not sr:
            raise HTTPException(status_code=404, detail=f"Service request #{id} not found")

        sla = _compute_sla_info(sr)
        rankings = _compute_dispatch_rankings(session, sr)

        proposal = None
        if sr.status in ["waiting_for_approval", "ready_for_review"]:
            top_tech = rankings[0] if rankings else None
            if top_tech:
                tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=13, minute=0, second=0, microsecond=0)
                proposal = {
                    "technician_id": top_tech["technician_id"],
                    "technician_name": top_tech["name"],
                    "start_time": tomorrow.isoformat(),
                    "end_time": (tomorrow + timedelta(hours=2)).isoformat(),
                    "service_request_id": sr.id,
                    "service_type": sr.service_type,
                    "location": sr.location,
                    "dispatch_reason": top_tech["reasons"][0] if top_tech["reasons"] else "Top ranked candidate",
                }

        existing_appt = session.query(Appointment).filter_by(service_request_id=sr.id).first()
        appointment_info = None
        if existing_appt:
            appointment_info = {
                "id": existing_appt.id,
                "technician_id": existing_appt.technician_id,
                "technician_name": existing_appt.technician.name if existing_appt.technician else "Unknown",
                "start_time": existing_appt.start_time.isoformat(),
                "end_time": existing_appt.end_time.isoformat(),
                "status": existing_appt.status,
            }

        audit_records = session.query(AuditLog).filter(
            or_(
                and_(AuditLog.entity_type == "service_request", AuditLog.entity_id == str(sr.id)),
                and_(AuditLog.entity_type == "appointment", existing_appt and AuditLog.entity_id == str(existing_appt.id))
            )
        ).order_by(AuditLog.created_at.asc()).all()

        timeline = []
        if not audit_records:
            timeline.append({
                "id": f"sr-{sr.id}-init",
                "timestamp": sr.created_at.isoformat(),
                "event": "service_request.received",
                "actor": "Customer Portal",
                "summary": f"Service request submitted for {sr.service_type} in {sr.location}",
            })
            if sr.status in ["waiting_for_approval", "ready_for_review"]:
                timeline.append({
                    "id": f"sr-{sr.id}-proposal",
                    "timestamp": sr.created_at.isoformat(),
                    "event": "proposal.generated",
                    "actor": "LangGraph Dispatch Engine",
                    "summary": f"Appointment proposal generated, awaiting operator approval",
                })
        else:
            for al in audit_records:
                timeline.append({
                    "id": str(al.id),
                    "timestamp": al.created_at.isoformat(),
                    "event": al.action,
                    "actor": (al.details or {}).get("actor", "System Agent"),
                    "summary": (al.details or {}).get("summary", f"Action {al.action} recorded"),
                })

        return {
            "id": sr.id,
            "customer_id": sr.customer_id,
            "customer": {
                "id": sr.customer.id if sr.customer else 0,
                "name": sr.customer.name if sr.customer else "Unknown",
                "email": sr.customer.email if sr.customer else "",
                "phone": sr.customer.phone if sr.customer else "",
            },
            "raw_message": sr.raw_message,
            "service_type": sr.service_type,
            "urgency": sr.urgency,
            "location": sr.location,
            "status": sr.status,
            "created_at": sr.created_at.isoformat(),
            "sla": sla,
            "dispatch_rankings": rankings,
            "proposal": proposal,
            "appointment": appointment_info,
            "timeline": timeline,
        }


@app.get("/appointments", summary="List appointments with status filter")
def list_appointments_endpoint(
    status: str | None = None,
    technician_id: int | None = None,
    limit: int = 50,
    user: InternalUser = Depends(get_current_internal_reader),
) -> list[dict[str, Any]]:
    """List appointments with technician and customer details."""
    with SessionLocal() as session:
        from fieldops.db.models import Appointment
        query = session.query(Appointment)
        if status:
            query = query.filter(Appointment.status == status)
        if technician_id:
            query = query.filter(Appointment.technician_id == technician_id)

        records = query.order_by(desc(Appointment.start_time)).limit(limit).all()
        return [
            {
                "id": a.id,
                "service_request_id": a.service_request_id,
                "customer_name": a.service_request.customer.name if a.service_request and a.service_request.customer else "Customer",
                "technician_id": a.technician_id,
                "technician_name": a.technician.name if a.technician else f"Technician #{a.technician_id}",
                "service_type": a.service_request.service_type if a.service_request else "Service",
                "location": a.service_request.location if a.service_request else "On-site",
                "start_time": a.start_time.isoformat(),
                "end_time": a.end_time.isoformat(),
                "status": a.status,
                "created_at": a.created_at.isoformat(),
            }
            for a in records
        ]


@app.get("/appointments/{id}", summary="Get detailed appointment record")
def get_appointment_detail_endpoint(
    id: int,
    user: InternalUser = Depends(get_current_internal_reader),
) -> dict[str, Any]:
    """Fetch complete appointment details including integration and notification statuses."""
    with SessionLocal() as session:
        from fieldops.db.models import Appointment, IntegrationRecord, NotificationJob, AuditLog
        from fieldops.application.service_lifecycle_service import ServiceLifecycleService
        appt = session.query(Appointment).filter_by(id=id).first()
        if not appt:
            raise HTTPException(status_code=404, detail=f"Appointment #{id} not found")

        lifecycle = ServiceLifecycleService(session)
        caps = lifecycle.compute_capabilities(appointment=appt, service_request=appt.service_request, role="operator")

        integrations = session.query(IntegrationRecord).filter_by(local_resource_id=appt.id).all()
        notifications = session.query(NotificationJob).filter_by(appointment_id=appt.id).all()
        audits = session.query(AuditLog).filter_by(entity_type="appointment", entity_id=str(appt.id)).all()

        return {
            "id": appt.id,
            "service_request_id": appt.service_request_id,
            "service_request": {
                "id": appt.service_request.id if appt.service_request else 0,
                "service_type": appt.service_request.service_type if appt.service_request else "",
                "urgency": appt.service_request.urgency if appt.service_request else "",
                "location": appt.service_request.location if appt.service_request else "",
                "raw_message": appt.service_request.raw_message if appt.service_request else "",
            },
            "customer": {
                "name": appt.service_request.customer.name if appt.service_request and appt.service_request.customer else "Unknown",
                "email": appt.service_request.customer.email if appt.service_request and appt.service_request.customer else "",
                "phone": appt.service_request.customer.phone if appt.service_request and appt.service_request.customer else "",
            },
            "technician": {
                "id": appt.technician.id if appt.technician else appt.technician_id,
                "name": appt.technician.name if appt.technician else f"Technician #{appt.technician_id}",
                "service_area": appt.technician.service_area if appt.technician else "",
            },
            "start_time": appt.start_time.isoformat(),
            "end_time": appt.end_time.isoformat(),
            "status": appt.status,
            "started_at": appt.started_at.isoformat() if appt.started_at else None,
            "completed_at": appt.completed_at.isoformat() if appt.completed_at else None,
            "completion_notes": appt.completion_notes,
            "resolution_summary": appt.resolution_summary,
            "replaced_by_appointment_id": appt.replaced_by_appointment_id,
            "rescheduled_from_appointment_id": appt.rescheduled_from_appointment_id,
            "capabilities": caps.model_dump(),
            "created_at": appt.created_at.isoformat(),
            "calendar_integrations": [
                {
                    "provider": i.provider,
                    "status": i.status,
                    "external_event_id": i.external_resource_id,
                    "attempt_count": i.attempt_count,
                    "last_error": i.last_error,
                }
                for i in integrations
            ],
            "email_notifications": [
                {
                    "job_type": n.job_type,
                    "status": n.status,
                    "scheduled_for": n.scheduled_for.isoformat(),
                    "provider_message_id": n.provider_message_id,
                    "sent_at": n.sent_at.isoformat() if n.sent_at else None,
                }
                for n in notifications
            ],
            "timeline": [
                {
                    "timestamp": a.created_at.isoformat(),
                    "event": a.action,
                    "summary": (a.details or {}).get("summary", a.action),
                }
                for a in audits
            ],
        }


@app.get("/escalations", summary="List operational escalations")
def list_escalations_endpoint(
    user: InternalUser = Depends(get_current_internal_reader),
) -> list[dict[str, Any]]:
    """List all open, acknowledged, and resolved escalations."""
    with SessionLocal() as session:
        from fieldops.db.models import ServiceRequest, AuditLog
        records = session.query(ServiceRequest).filter(
            or_(
                ServiceRequest.urgency.in_(["high", "emergency"]),
                ServiceRequest.status.in_(["needs_rescheduling", "conflict", "no_technician", "no_technician_available", "rejected"])
            )
        ).order_by(desc(ServiceRequest.created_at)).all()

        escalations = []
        for sr in records:
            sla = _compute_sla_info(sr, session)
            recent_audit = session.query(AuditLog).filter(
                AuditLog.entity_type == "service_request",
                AuditLog.entity_id == str(sr.id),
                AuditLog.action.in_(["escalation.acknowledged", "escalation.resolved"])
            ).order_by(desc(AuditLog.created_at)).first()

            esc_status = "open"
            if recent_audit:
                if recent_audit.action == "escalation.resolved":
                    esc_status = "resolved"
                elif recent_audit.action == "escalation.acknowledged":
                    esc_status = "acknowledged"

            reason = f"{sr.urgency.capitalize()} urgency {sr.service_type} issue in {sr.location}"
            if sr.status == "needs_rescheduling":
                reason = "Booking conflict occurred; requires immediate rescheduling"

            severity = "critical" if sr.urgency == "emergency" or sla["sla_status"] == "breached" else "high"

            escalations.append({
                "id": sr.id,
                "service_request_id": sr.id,
                "customer_name": sr.customer.name if sr.customer else "Unknown",
                "customer_email": sr.customer.email if sr.customer else "",
                "reason": reason,
                "severity": severity,
                "status": esc_status,
                "created_at": sr.created_at.isoformat(),
                "sla_status": sla["sla_status"],
                "sla_deadline": sla["resolution_deadline"],
                "service_type": sr.service_type,
                "urgency": sr.urgency,
                "location": sr.location,
            })
        return escalations


@app.get("/escalations/{id}", summary="Get escalation detail")
def get_escalation_detail_endpoint(
    id: int,
    user: InternalUser = Depends(get_current_internal_reader),
) -> dict[str, Any]:
    """Fetch details of an escalation."""
    with SessionLocal() as session:
        from fieldops.db.models import ServiceRequest, AuditLog
        sr = session.query(ServiceRequest).filter_by(id=id).first()
        if not sr:
            raise HTTPException(status_code=404, detail=f"Escalation #{id} not found")

        sla = _compute_sla_info(sr)
        recent_audit = session.query(AuditLog).filter(
            AuditLog.entity_type == "service_request",
            AuditLog.entity_id == str(sr.id),
            AuditLog.action.in_(["escalation.acknowledged", "escalation.resolved"])
        ).order_by(desc(AuditLog.created_at)).first()

        esc_status = "open"
        if recent_audit:
            if recent_audit.action == "escalation.resolved":
                esc_status = "resolved"
            elif recent_audit.action == "escalation.acknowledged":
                esc_status = "acknowledged"

        return {
            "id": sr.id,
            "service_request_id": sr.id,
            "customer_name": sr.customer.name if sr.customer else "Unknown",
            "customer_email": sr.customer.email if sr.customer else "",
            "customer_phone": sr.customer.phone if sr.customer else "",
            "service_type": sr.service_type,
            "urgency": sr.urgency,
            "location": sr.location,
            "raw_message": sr.raw_message,
            "status": esc_status,
            "severity": "critical" if sr.urgency == "emergency" or sla["sla_status"] == "breached" else "high",
            "sla": sla,
            "created_at": sr.created_at.isoformat(),
        }


@app.post("/escalations/{id}/acknowledge", summary="Operator acknowledges escalation")
def acknowledge_escalation_endpoint(
    id: int,
    user: InternalUser = Depends(get_current_operator_or_admin),
) -> dict[str, Any]:
    """Acknowledge an operational escalation."""
    with SessionLocal() as session:
        from fieldops.db.models import ServiceRequest, AuditLog
        sr = session.query(ServiceRequest).filter_by(id=id).first()
        if not sr:
            raise HTTPException(status_code=404, detail=f"Escalation #{id} not found")

        audit = AuditLog(
            entity_type="service_request",
            entity_id=str(id),
            action="escalation.acknowledged",
            details={"summary": "Escalation acknowledged by operator", "actor": "Operator"},
        )
        session.add(audit)
        session.commit()
        return {"id": id, "status": "acknowledged", "message": "Escalation acknowledged."}


@app.post("/escalations/{id}/resolve", summary="Operator resolves escalation")
def resolve_escalation_endpoint(
    id: int,
    user: InternalUser = Depends(get_current_operator_or_admin),
) -> dict[str, Any]:
    """Mark an operational escalation as resolved."""
    with SessionLocal() as session:
        from fieldops.db.models import ServiceRequest, AuditLog
        sr = session.query(ServiceRequest).filter_by(id=id).first()
        if not sr:
            raise HTTPException(status_code=404, detail=f"Escalation #{id} not found")

        audit = AuditLog(
            entity_type="service_request",
            entity_id=str(id),
            action="escalation.resolved",
            details={"summary": "Escalation resolved by operator", "actor": "Operator"},
        )
        session.add(audit)
        session.commit()
        return {"id": id, "status": "resolved", "message": "Escalation marked as resolved."}


@app.get("/system/status", summary="Operational system status overview")
def get_system_status_endpoint(
    user: InternalUser = Depends(get_current_internal_reader),
) -> dict[str, Any]:
    """Return operational system health status for operator dashboard."""
    with SessionLocal() as session:
        from fieldops.db.models import OutboxEvent, IntegrationRecord
        db_ok = True
        try:
            session.execute(text("SELECT 1"))
        except Exception:
            db_ok = False

        pending_outbox = session.query(OutboxEvent).filter_by(status="pending").count()
        failed_integrations = session.query(IntegrationRecord).filter_by(status="failed").count()

        return {
            "api": {"status": "ok", "version": "0.1.0"},
            "database": {"status": "ok" if db_ok else "error", "pool_size": settings.DB_POOL_SIZE},
            "redis": {"status": "ok" if not settings.LOAD_TEST_MODE else "simulated"},
            "outbox": {"pending_count": pending_outbox},
            "integrations": {"failed_count": failed_integrations},
        }


@app.get(
    "/appointments/{appointment_id}/notifications",
    status_code=status.HTTP_200_OK,
    summary="Query background notification jobs for an appointment",
)
def get_appointment_notifications(
    appointment_id: int,
    user: InternalUser = Depends(get_current_internal_reader),
) -> list[dict[str, Any]]:
    """Fetch all notification jobs associated with a specific appointment."""
    with SessionLocal() as session:
        notif_repo = NotificationJobRepository(session)
        jobs = notif_repo.get_by_appointment_id(appointment_id)
        return [
            {
                "id": job.id,
                "appointment_id": job.appointment_id,
                "job_type": job.job_type,
                "status": job.status,
                "scheduled_for": job.scheduled_for.isoformat(),
                "attempt_count": job.attempt_count,
                "last_error": job.last_error,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
            }
            for job in jobs
        ]


@app.post(
    "/appointments/{appointment_id}/start",
    status_code=status.HTTP_200_OK,
    summary="Mark appointment in progress",
)
def start_appointment_endpoint(
    appointment_id: int,
    payload: dict[str, Any] | None = None,
    user: InternalUser = Depends(get_current_operator_or_admin),
) -> dict[str, Any]:
    """Operator action to start service work on-site."""
    with SessionLocal() as session:
        from fieldops.application.service_lifecycle_service import ServiceLifecycleService
        service = ServiceLifecycleService(session)
        appt = service.start_service(appointment_id, actor_type="operator")
        session.commit()
        return {
            "appointment_id": appt.id,
            "status": appt.status,
            "started_at": appt.started_at.isoformat() if appt.started_at else None,
            "message": "Service started (in progress).",
        }


@app.post(
    "/appointments/{appointment_id}/complete",
    status_code=status.HTTP_200_OK,
    summary="Mark appointment completed and enqueue follow-up outbox event",
)
def complete_appointment_endpoint(
    appointment_id: int,
    payload: dict[str, Any] | None = None,
    user: InternalUser = Depends(get_current_operator_or_admin),
) -> dict[str, Any]:
    """Operator action to complete appointment and schedule follow-up message."""
    notes = payload.get("completion_notes") if payload else None
    summary_text = payload.get("resolution_summary") if payload else None
    with SessionLocal() as session:
        from fieldops.application.service_lifecycle_service import ServiceLifecycleService
        service = ServiceLifecycleService(session)
        appt = service.complete_service(
            appointment_id,
            completion_notes=notes,
            resolution_summary=summary_text,
            actor_type="operator",
        )
        session.commit()
        return {
            "appointment_id": appt.id,
            "status": appt.status,
            "completed_at": appt.completed_at.isoformat() if appt.completed_at else None,
            "completion_notes": appt.completion_notes,
            "resolution_summary": appt.resolution_summary,
            "message": "Appointment completed and follow-up outbox event recorded.",
        }


@app.post(
    "/appointments/{appointment_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel appointment",
)
def cancel_appointment_endpoint(
    appointment_id: int,
    payload: dict[str, Any] | None = None,
    user: InternalUser = Depends(get_current_operator_or_admin),
) -> dict[str, Any]:
    """Operator action to cancel appointment."""
    reason = payload.get("reason") if payload else None
    with SessionLocal() as session:
        from fieldops.application.service_lifecycle_service import ServiceLifecycleService
        service = ServiceLifecycleService(session)
        _, appt = service.cancel_request(appointment_id=appointment_id, reason=reason, actor_type="operator")
        session.commit()
        return {
            "appointment_id": appt.id if appt else appointment_id,
            "status": appt.status if appt else "cancelled",
            "message": "Appointment cancelled.",
        }


@app.post(
    "/appointments/{appointment_id}/reassign",
    status_code=status.HTTP_200_OK,
    summary="Reassign appointment to a different technician",
)
def reassign_appointment_endpoint(
    appointment_id: int,
    payload: dict[str, Any] | None = None,
    user: InternalUser = Depends(get_current_operator_or_admin),
) -> dict[str, Any]:
    """Operator action to reassign an appointment to another certified technician."""
    tech_id = payload.get("technician_id") if payload else None
    reason = payload.get("reason") if payload else None
    with SessionLocal() as session:
        from fieldops.application.service_lifecycle_service import ServiceLifecycleService
        service = ServiceLifecycleService(session)
        appt = service.reassign_technician(
            appointment_id=appointment_id,
            new_technician_id=tech_id,
            reason=reason,
            actor_type="operator",
        )
        session.commit()
        return {
            "appointment_id": appt.id,
            "technician_id": appt.technician_id,
            "status": appt.status,
            "message": "Appointment reassigned successfully.",
        }


@app.get(
    "/reschedule-requests",
    status_code=status.HTTP_200_OK,
    summary="List all reschedule requests",
)
def list_reschedule_requests_endpoint(
    req_status: str | None = None,
    user: InternalUser = Depends(get_current_internal_reader),
) -> list[dict[str, Any]]:
    """List customer/operator reschedule requests."""
    with SessionLocal() as session:
        from fieldops.db.models import RescheduleRequest
        query = session.query(RescheduleRequest)
        if req_status:
            query = query.filter(RescheduleRequest.status == req_status)
        requests = query.order_by(RescheduleRequest.id.desc()).all()
        result = []
        for r in requests:
            result.append({
                "id": r.id,
                "service_request_id": r.service_request_id,
                "appointment_id": r.appointment_id,
                "requested_by_type": r.requested_by_type,
                "requested_by_id": r.requested_by_id,
                "preferred_time": r.preferred_time,
                "reason": r.reason,
                "status": r.status,
                "reviewed_by": r.reviewed_by,
                "rejection_reason": r.rejection_reason,
                "replacement_appointment_id": r.replacement_appointment_id,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
            })
        return result


@app.post(
    "/reschedule-requests/{request_id}/approve",
    status_code=status.HTTP_200_OK,
    summary="Approve reschedule request and create replacement appointment",
)
def approve_reschedule_request_endpoint(
    request_id: int,
    payload: dict[str, Any],
    user: InternalUser = Depends(get_current_operator_or_admin),
) -> dict[str, Any]:
    """Operator action to approve reschedule and create replacement appointment."""
    start_time_raw = payload.get("start_time")
    end_time_raw = payload.get("end_time")
    if not start_time_raw or not end_time_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time and end_time are required to approve reschedule.",
        )
    start_time = datetime.fromisoformat(start_time_raw)
    end_time = datetime.fromisoformat(end_time_raw)
    tech_id = payload.get("technician_id")
    notes = payload.get("notes")

    with SessionLocal() as session:
        from fieldops.application.service_lifecycle_service import ServiceLifecycleService
        service = ServiceLifecycleService(session)
        resched_req, new_appt = service.approve_reschedule(
            reschedule_request_id=request_id,
            start_time=start_time,
            end_time=end_time,
            technician_id=tech_id,
            operator_id="operator",
            notes=notes,
        )
        session.commit()
        return {
            "reschedule_request_id": resched_req.id,
            "status": resched_req.status,
            "replacement_appointment_id": new_appt.id,
            "new_start_time": new_appt.start_time.isoformat(),
            "new_end_time": new_appt.end_time.isoformat(),
            "message": "Reschedule request approved and replacement appointment created.",
        }


@app.post(
    "/reschedule-requests/{request_id}/reject",
    status_code=status.HTTP_200_OK,
    summary="Reject reschedule request",
)
def reject_reschedule_request_endpoint(
    request_id: int,
    payload: dict[str, Any],
    user: InternalUser = Depends(get_current_operator_or_admin),
) -> dict[str, Any]:
    """Operator action to reject reschedule request."""
    rejection_reason = payload.get("rejection_reason") or "Reschedule request rejected by operator."
    with SessionLocal() as session:
        from fieldops.application.service_lifecycle_service import ServiceLifecycleService
        service = ServiceLifecycleService(session)
        resched_req = service.reject_reschedule(
            reschedule_request_id=request_id,
            rejection_reason=rejection_reason,
            operator_id="operator",
        )
        session.commit()
        return {
            "reschedule_request_id": resched_req.id,
            "status": resched_req.status,
            "rejection_reason": resched_req.rejection_reason,
            "message": "Reschedule request rejected.",
        }



@app.get(
    "/appointments/{appointment_id}/integrations",
    status_code=status.HTTP_200_OK,
    summary="Query external integration status (Calendar & Email) for an appointment",
)
def get_appointment_integrations(
    appointment_id: int,
    user: InternalUser = Depends(get_current_internal_reader),
) -> dict[str, Any]:
    """Fetch external integration state for an appointment."""
    with SessionLocal() as session:
        appt_repo = AppointmentRepository(session)
        appt = appt_repo.get_by_id(appointment_id)
        if not appt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Appointment {appointment_id} not found",
            )

        integration_repo = IntegrationRepository(session)
        notif_repo = NotificationJobRepository(session)

        cal_records = integration_repo.get_by_appointment_id(appointment_id)
        calendar_status: list[dict[str, Any]] = [
            {
                "id": r.id,
                "provider": r.provider,
                "status": r.status,
                "external_event_id": r.external_resource_id,
                "attempt_count": r.attempt_count,
                "last_error": r.last_error,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in cal_records
        ]

        notif_jobs = notif_repo.get_by_appointment_id(appointment_id)
        email_status: list[dict[str, Any]] = [
            {
                "id": j.id,
                "job_type": j.job_type,
                "provider": j.provider,
                "provider_message_id": j.provider_message_id,
                "status": j.status,
                "attempt_count": j.attempt_count,
                "sent_at": j.sent_at.isoformat() if j.sent_at else None,
                "last_error": j.last_error,
            }
            for j in notif_jobs
        ]

        return {
            "appointment_id": appointment_id,
            "appointment_status": appt.status,
            "calendar_integrations": calendar_status,
            "email_notifications": email_status,
        }


# ==============================================================================
# Inbound Intake Endpoints (Phase 16)
# ==============================================================================


@app.post(
    "/intake/fake-email",
    response_model=InboundResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Simulated email intake endpoint for development and testing",
)
def intake_fake_email(payload: FakeEmailPayload) -> InboundResponse:
    """Intake simulated incoming customer email and normalize to FieldOps workflow."""
    if settings.APP_ENV == "production" and not settings.ENABLE_FAKE_INTAKE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fake email intake is disabled in production.",
        )

    inbound_req = FakeEmailInboundAdapter.normalize(payload)
    inbound_service = InboundRequestService(workflow_runner=run_field_service_workflow)
    return inbound_service.handle(inbound_req, raw_payload=payload)


@app.post(
    "/intake/webhook",
    response_model=InboundResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generic controlled webhook intake endpoint",
)
def intake_webhook(
    payload: WebhookPayload,
    webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
) -> InboundResponse:
    """Intake generic external webhook event and normalize to FieldOps workflow."""
    if not webhook_secret or webhook_secret != settings.WEBHOOK_SHARED_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Webhook-Secret header.",
        )

    inbound_req = WebhookInboundAdapter.normalize(payload)
    inbound_service = InboundRequestService(workflow_runner=run_field_service_workflow)
    return inbound_service.handle(inbound_req, raw_payload=payload)


# Mount Customer Portal API Router
from fieldops.api.customer_portal import customer_router
app.include_router(customer_router)

# Mount Admin Console API Router
from fieldops.api.admin_console import admin_router
app.include_router(admin_router)

# Mount Customer Conversational Agent Router (Phase 22)
from fieldops.api.customer_conversations import router as customer_conversations_router
app.include_router(customer_conversations_router)






