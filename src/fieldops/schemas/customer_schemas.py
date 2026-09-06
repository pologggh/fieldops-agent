"""Customer Portal Pydantic DTO schemas.

Enforces strict data minimization by exposing only customer-appropriate fields,
excluding internal SLA calculations, technician workloads, dispatch rankings,
and internal escalation/audit events.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List


class CustomerRegisterInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Full customer name")
    email: EmailStr = Field(..., description="Customer unique login email")
    password: str = Field(..., min_length=6, max_length=100, description="Plaintext password to hash")
    phone: Optional[str] = Field(None, max_length=50, description="Optional contact phone number")


class CustomerLoginInput(BaseModel):
    email: EmailStr = Field(..., description="Customer login email")
    password: str = Field(..., description="Customer account password")


class CustomerProfileView(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str] = None


class CustomerAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer: CustomerProfileView
    success: bool = True


class CustomerProfileUpdateInput(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)


class CustomerServiceRequestCreateInput(BaseModel):
    service_type: Optional[str] = Field(None, max_length=100, description="Service category")
    problem_description: str = Field(..., min_length=5, max_length=2000, description="Detailed customer issue description")
    location: Optional[str] = Field(None, max_length=255, description="Customer premises / service address")
    preferred_time: Optional[str] = Field(None, max_length=100, description="Preferred appointment window or day")
    phone: Optional[str] = Field(None, max_length=50, description="Contact phone for this specific request")


class CustomerServiceRequestSupplementInput(BaseModel):
    location: Optional[str] = Field(None, max_length=255, description="Corrected or detailed location")
    preferred_time: Optional[str] = Field(None, max_length=100, description="Preferred appointment date/time")
    additional_details: Optional[str] = Field(None, max_length=2000, description="Additional context or problem details")


class CustomerServiceRequestCancelInput(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, description="Reason for cancellation")


class CustomerRescheduleInput(BaseModel):
    preferred_time: str = Field(..., min_length=3, max_length=100, description="Requested alternative time window")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for reschedule")


class CustomerTimelineItem(BaseModel):
    id: str
    timestamp: str
    title: str
    description: str


class CustomerAppointmentView(BaseModel):
    id: int
    service_request_id: int
    start_time: str
    end_time: str
    service_type: str
    location: str
    technician_name: str
    status: str
    can_cancel: bool
    can_reschedule: bool
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    completion_notes: Optional[str] = None
    resolution_summary: Optional[str] = None
    rescheduled_from_appointment_id: Optional[int] = None
    replaced_by_appointment_id: Optional[int] = None



class CustomerServiceRequestView(BaseModel):
    id: int
    service_type: str
    problem_description: str
    location: str
    preferred_time: Optional[str] = None
    customer_status: str
    internal_status: str
    submitted_at: str
    needs_information: bool
    missing_fields: List[str] = []
    can_cancel: bool
    can_reschedule: bool
    appointment: Optional[CustomerAppointmentView] = None
    timeline: List[CustomerTimelineItem] = []


class CustomerHomeSummary(BaseModel):
    open_requests_count: int
    needs_info_count: int
    active_requests_count: Optional[int] = None
    upcoming_appointments_count: Optional[int] = None
    needs_action_count: Optional[int] = None
    upcoming_appointment: Optional[CustomerAppointmentView] = None
    recent_requests: List[CustomerServiceRequestView] = []
