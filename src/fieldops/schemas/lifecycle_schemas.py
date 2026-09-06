"""Pydantic schemas for Service Lifecycle Completion (Phase 24)."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class LifecycleCapabilitiesView(BaseModel):
    """Reflects allowable state transitions for the current user and appointment state."""
    can_start: bool
    can_complete: bool
    can_cancel: bool
    can_reschedule: bool
    can_reassign: bool


class AppointmentStartInput(BaseModel):
    started_at: Optional[datetime] = None


class AppointmentCompleteInput(BaseModel):
    completion_notes: Optional[str] = None
    resolution_summary: Optional[str] = None
    completed_at: Optional[datetime] = None


class AppointmentCancelInput(BaseModel):
    reason: Optional[str] = None


class AppointmentReassignInput(BaseModel):
    technician_id: Optional[int] = None
    reason: Optional[str] = None


class RescheduleRequestCreateInput(BaseModel):
    preferred_time: str
    reason: Optional[str] = None


class RescheduleApprovalInput(BaseModel):
    technician_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    notes: Optional[str] = None


class RescheduleRejectionInput(BaseModel):
    rejection_reason: str


class RescheduleRequestView(BaseModel):
    id: int
    service_request_id: int
    appointment_id: int
    requested_by_type: str
    requested_by_id: Optional[str] = None
    preferred_time: Optional[str] = None
    reason: Optional[str] = None
    status: str
    reviewed_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    replacement_appointment_id: Optional[int] = None
    created_at: str
    updated_at: str


class AppointmentDetailLifecycleView(BaseModel):
    id: int
    service_request_id: int
    technician_id: int
    technician_name: Optional[str] = None
    start_time: str
    end_time: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    completion_notes: Optional[str] = None
    resolution_summary: Optional[str] = None
    replaced_by_appointment_id: Optional[int] = None
    rescheduled_from_appointment_id: Optional[int] = None
    created_at: str
    capabilities: LifecycleCapabilitiesView
