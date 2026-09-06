"""Pydantic schemas and contracts for Customer Conversational Agent."""

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class ConversationDraftSchema(BaseModel):
    """Structured representation of the in-flight service request draft."""

    service_type: Optional[str] = None
    urgency: str = "medium"
    location: Optional[str] = None
    preferred_time: Optional[str] = None
    problem_description: Optional[str] = None
    required_skills: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    is_complete: bool = False
    safety_warning: Optional[str] = None


class ConversationMessageView(BaseModel):
    """Customer-safe message representation in a dialogue session."""

    id: int
    conversation_id: int
    role: str  # customer, assistant, system_event
    content: str
    client_message_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: str


class ConversationView(BaseModel):
    """Complete view of an active or concluded customer conversation."""

    id: int
    customer_id: int
    status: str  # active, awaiting_confirmation, submitted, cancelled, closed
    draft_version: int
    draft: ConversationDraftSchema
    messages: List[ConversationMessageView] = Field(default_factory=list)
    submitted_service_request_id: Optional[int] = None
    created_at: str
    updated_at: str
    last_message_at: Optional[str] = None


class ConversationSummaryItem(BaseModel):
    """Compact preview item for conversation lists."""

    id: int
    status: str
    service_type: Optional[str] = None
    draft_preview: Optional[str] = None
    submitted_service_request_id: Optional[int] = None
    created_at: str
    updated_at: str


class ConversationCreateInput(BaseModel):
    """Payload to initialize a new conversation session."""

    initial_message: Optional[str] = Field(None, max_length=2000)
    client_message_id: Optional[str] = None


class ConversationSendMessageInput(BaseModel):
    """Customer message payload for ongoing dialogue."""

    content: str = Field(..., min_length=1, max_length=2000)
    client_message_id: Optional[str] = None


class ConversationConfirmInput(BaseModel):
    """Explicit confirmation request to convert draft into formal ServiceRequest."""

    idempotency_key: Optional[str] = None


class ConversationConfirmResponse(BaseModel):
    """Response returned upon successful confirmation."""

    success: bool = True
    conversation_id: int
    service_request_id: int
    status: str
    message: str
