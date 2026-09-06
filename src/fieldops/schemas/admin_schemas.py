"""Pydantic schemas for the FieldOps Admin Console (System Governance)."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, EmailStr, Field


# ==============================================================================
# 1. Internal User Schemas
# ==============================================================================

RoleType = Literal["admin", "operator", "viewer"]


class InternalUserView(BaseModel):
    id: int
    email: str
    name: str
    role: RoleType
    is_active: bool
    last_login: Optional[str] = None
    created_at: str


class InternalUserCreateInput(BaseModel):
    email: EmailStr
    name: str
    role: RoleType
    password: str = Field(min_length=6)


class InternalUserUpdateInput(BaseModel):
    name: Optional[str] = None


class RoleChangeInput(BaseModel):
    role: RoleType


# ==============================================================================
# 2. Technician Admin Schemas
# ==============================================================================


class TechnicianAdminView(BaseModel):
    id: int
    name: str
    service_area: str
    status: str
    skills: List[str]
    max_daily_work_minutes: int
    max_daily_jobs: Optional[int] = None
    is_available_for_emergency: bool
    current_workload_minutes: int = 0
    current_active_jobs: int = 0
    created_at: str


class TechnicianCreateInput(BaseModel):
    name: str
    service_area: str
    skills: List[str]
    max_daily_work_minutes: int = Field(default=480, ge=60, le=1440)
    max_daily_jobs: Optional[int] = Field(default=5, ge=1, le=50)
    is_available_for_emergency: bool = False
    status: str = "active"


class TechnicianUpdateInput(BaseModel):
    name: Optional[str] = None
    service_area: Optional[str] = None
    skills: Optional[List[str]] = None
    max_daily_work_minutes: Optional[int] = Field(default=None, ge=60, le=1440)
    max_daily_jobs: Optional[int] = Field(default=None, ge=1, le=50)
    is_available_for_emergency: Optional[bool] = None


# ==============================================================================
# 3. Policy Schemas
# ==============================================================================


class DispatchPolicyView(BaseModel):
    id: int
    version: int
    is_active: bool
    weights: Dict[str, Any]
    description: Optional[str] = None
    created_by: str
    created_at: str


class DispatchPolicyCreateInput(BaseModel):
    weights: Dict[str, int]
    description: Optional[str] = None
    set_active: Optional[bool] = True


class SLAPolicyView(BaseModel):
    id: int
    version: int
    is_active: bool
    targets: Dict[str, Any]
    description: Optional[str] = None
    created_by: str
    created_at: str


class SLAPolicyCreateInput(BaseModel):
    targets: Dict[str, Dict[str, int]]
    description: Optional[str] = None
    set_active: Optional[bool] = True


# ==============================================================================
# 4. Integration Schemas
# ==============================================================================


class IntegrationProviderView(BaseModel):
    provider: str
    type: str
    is_mock: bool
    badge: str
    status: str
    success_count: int
    failure_count: int
    last_sync: Optional[str] = None


class IntegrationSummaryView(BaseModel):
    providers: List[IntegrationProviderView]
    total_synced: int
    total_failed: int
    calendar_provider: Optional[str] = None
    calendar_is_fake: Optional[bool] = None
    email_provider: Optional[str] = None
    email_is_fake: Optional[bool] = None
    pending_count: Optional[int] = None
    synced_count: Optional[int] = None
    failed_count: Optional[int] = None


class IntegrationFailureView(BaseModel):
    id: int
    provider: str
    resource_type: str
    local_resource_id: int
    appointment_id: Optional[int] = None
    status: str
    attempt_count: int
    last_error_summary: Optional[str] = None
    last_error: Optional[str] = None
    updated_at: str


# ==============================================================================
# 5. Audit Review Schemas
# ==============================================================================


class AuditLogView(BaseModel):
    id: int
    timestamp: str
    entity_type: str
    entity_id: str
    action: str
    actor: str
    actor_type: str
    summary: str
    details: Optional[Dict[str, Any]] = None


# ==============================================================================
# 6. System Governance Schemas (Zero Secret Exposure)
# ==============================================================================


class SystemSummaryView(BaseModel):
    health_status: str
    readiness_status: str
    database: str
    redis: str
    active_internal_users: int
    active_technicians: int
    open_service_requests: int
    pending_outbox_events: int
    llm_config: Dict[str, Any]
    api_status: Optional[str] = None
    database_status: Optional[str] = None
    redis_status: Optional[str] = None
    celery_worker_status: Optional[str] = None
    outbox_backlog_count: Optional[int] = None
    integration_failures_count: Optional[int] = None
    active_technicians_count: Optional[int] = None
    active_internal_users_count: Optional[int] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_configured: Optional[bool] = None
    open_escalations_count: Optional[int] = 0
    sla_breaches_count: Optional[int] = 0
