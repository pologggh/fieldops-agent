from typing import Any, Literal
from pydantic import BaseModel, EmailStr, Field


class ParsedServiceRequest(BaseModel):
    """Structured representation of a parsed customer service request."""

    service_type: str = Field(
        description="Category of service required (e.g. 'HVAC', 'Plumbing', 'Electrical', 'Networking', 'Appliance Repair', 'Other')."
    )
    urgency: str = Field(
        description="Semantic urgency inferred from customer message: 'low', 'medium', 'high', or 'emergency'. (Semantic interpretation only, not a final business determination)."
    )
    location: str | None = Field(
        default=None,
        description="Service area or city mentioned by the customer (e.g. 'Shinjuku', 'Yokohama'). Set to null if not specified. Never hallucinate locations.",
    )
    required_skills: list[str] = Field(
        default_factory=list,
        description="Inferred skills needed to service the request (e.g. ['HVAC'], ['Plumbing'], ['Electrical']). Empty list if undetermined.",
    )
    preferred_time: str | None = Field(
        default=None,
        description="Customer's expressed preferred appointment time in original natural language format (e.g. 'this afternoon', 'tomorrow morning'). Null if not mentioned.",
    )
    problem_description: str = Field(
        description="Concise, factual summary of the reported problem without adding unstated facts or assumptions."
    )


class ParseRequestInput(BaseModel):
    """Request payload for the POST /parse-service-request and legacy /service-requests/analyze endpoints."""

    message: str = Field(
        ...,
        description="Raw natural language service request from the customer.",
    )


class AnalyzeServiceRequestResponse(BaseModel):
    """Response payload for the POST /service-requests/analyze endpoint."""

    request_id: str
    service_type: str | None = None
    urgency: str | None = None
    location: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_time: str | None = None
    problem_description: str | None = None
    candidate_technician_ids: list[int] = Field(default_factory=list)
    matching_status: str | None = None
    requested_window_start: str | None = None
    requested_window_end: str | None = None
    available_options: list[dict[str, Any]] = Field(default_factory=list)
    scheduling_status: str | None = None
    appointment_proposal: dict[str, Any] | None = None
    approval_status: str | None = None
    approval_reason: str | None = None
    human_review_required: bool = False
    validation_errors: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    failed_step: str | None = None
    retryable: bool = False
    workflow_status: str


class ServiceRequestCreateInput(BaseModel):
    """Request payload for POST /service-requests."""

    customer_name: str = Field(..., min_length=1, description="Customer full name")
    email: EmailStr = Field(..., description="Customer email address for identification")
    phone: str | None = Field(default=None, description="Customer contact phone number")
    message: str = Field(..., min_length=1, description="Customer issue description")


class ServiceRequestCreateResponse(BaseModel):
    """Response payload for POST /service-requests representing persisted state and scheduling options."""

    request_id: str
    customer_id: int | None = None
    service_request_id: int | None = None
    service_type: str | None = None
    urgency: str | None = None
    location: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_time: str | None = None
    problem_description: str | None = None
    candidate_technician_ids: list[int] = Field(default_factory=list)
    matching_status: str | None = None
    requested_window_start: str | None = None
    requested_window_end: str | None = None
    available_options: list[dict[str, Any]] = Field(default_factory=list)
    scheduling_status: str | None = None
    appointment_proposal: dict[str, Any] | None = None
    approval_status: str | None = None
    approval_reason: str | None = None
    human_review_required: bool = False
    appointment_id: int | None = None
    appointment_status: str | None = None
    finalization_status: str | None = None
    conflict_detected: bool = False
    validation_errors: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    failed_step: str | None = None
    retryable: bool = False
    workflow_status: str


class ServiceRequestApprovalInput(BaseModel):
    """Request payload for POST /service-requests/{request_id}/approval."""

    decision: Literal["approve", "reject"] = Field(
        ...,
        description="Operator approval decision: 'approve' or 'reject'.",
    )
    reason: str | None = Field(
        default=None,
        description="Optional justification or reason for the decision, particularly for rejections.",
    )


class ServiceRequestApprovalResponse(BaseModel):
    """Response payload for POST /service-requests/{request_id}/approval."""

    request_id: str
    service_request_id: int | None = None
    workflow_status: str
    approval_status: str | None = None
    approval_reason: str | None = None
    appointment_proposal: dict[str, Any] | None = None
    appointment_id: int | None = None
    appointment_status: str | None = None
    finalization_status: str | None = None
    conflict_detected: bool = False
    error_code: str | None = None
    error_message: str | None = None
    failed_step: str | None = None
    retryable: bool = False


