export type SLAStatus = 'on_track' | 'at_risk' | 'breached' | 'completed';
export type Urgency = 'low' | 'medium' | 'high' | 'emergency';
export type ServiceRequestStatus =
  | 'received'
  | 'validated'
  | 'matched'
  | 'ready_for_review'
  | 'waiting_for_approval'
  | 'approved'
  | 'rejected'
  | 'scheduled'
  | 'completed'
  | 'needs_rescheduling'
  | 'conflict'
  | 'cancelled';

export interface Customer {
  id: number;
  name: string;
  email: string;
  phone: string;
}

export interface SLAInfo {
  sla_status: SLAStatus;
  response_deadline: string;
  resolution_deadline: string;
  response_hours: number;
  resolution_hours: number;
}

export interface DispatchCandidate {
  rank: number;
  technician_id: number;
  name: string;
  service_area: string;
  skills: string[];
  score: number;
  availability: string;
  workload: number;
  capacity: string;
  sla_fit: string;
  travel_estimate: string;
  reasons: string[];
}

export interface AppointmentProposal {
  technician_id: number;
  technician_name: string;
  start_time: string;
  end_time: string;
  service_request_id: number;
  service_type: string;
  location: string;
  dispatch_reason: string;
}

export interface AppointmentSummary {
  id: number;
  technician_id: number;
  technician_name: string;
  start_time: string;
  end_time: string;
  status: string;
}

export interface TimelineEvent {
  id: string;
  timestamp: string;
  event: string;
  actor: string;
  summary: string;
}

export interface ServiceRequestListItem {
  id: number;
  customer_id: number;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  raw_message: string;
  service_type: string;
  urgency: Urgency;
  location: string;
  status: ServiceRequestStatus;
  created_at: string;
  sla_status: SLAStatus;
  sla_deadline: string;
}

export interface ServiceRequestDetail {
  id: number;
  customer_id: number;
  customer: Customer;
  raw_message: string;
  service_type: string;
  urgency: Urgency;
  location: string;
  status: ServiceRequestStatus;
  created_at: string;
  sla: SLAInfo;
  dispatch_rankings: DispatchCandidate[];
  proposal: AppointmentProposal | null;
  appointment: AppointmentSummary | null;
  timeline: TimelineEvent[];
}

export interface AppointmentListItem {
  id: number;
  service_request_id: number;
  customer_name: string;
  technician_id: number;
  technician_name: string;
  service_type: string;
  location: string;
  start_time: string;
  end_time: string;
  status: string;
  created_at: string;
}

export interface CalendarIntegration {
  provider: string;
  status: string;
  external_event_id: string | null;
  attempt_count: number;
  last_error: string | null;
}

export interface EmailNotification {
  job_type: string;
  status: string;
  scheduled_for: string;
  provider_message_id: string | null;
  sent_at: string | null;
}

export interface LifecycleCapabilities {
  can_start: boolean;
  can_complete: boolean;
  can_cancel: boolean;
  can_reschedule: boolean;
  can_reassign: boolean;
}

export interface AppointmentDetail {
  id: number;
  service_request_id: number;
  service_request: {
    id: number;
    service_type: string;
    urgency: string;
    location: string;
    raw_message: string;
  };
  customer: {
    name: string;
    email: string;
    phone: string;
  };
  technician: {
    id: number;
    name: string;
    service_area: string;
  };
  start_time: string;
  end_time: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  completion_notes?: string | null;
  resolution_summary?: string | null;
  replaced_by_appointment_id?: number | null;
  rescheduled_from_appointment_id?: number | null;
  capabilities?: LifecycleCapabilities;
  created_at: string;
  calendar_integrations: CalendarIntegration[];
  email_notifications: EmailNotification[];
  timeline: TimelineEvent[];
}

export interface EscalationItem {
  id: number;
  service_request_id: number;
  customer_name: string;
  customer_email: string;
  reason: string;
  severity: 'critical' | 'high' | 'medium';
  status: 'open' | 'acknowledged' | 'resolved';
  created_at: string;
  sla_status: SLAStatus;
  sla_deadline: string;
  service_type: string;
  urgency: Urgency;
  location: string;
}

export interface EscalationDetail {
  id: number;
  service_request_id: number;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  service_type: string;
  urgency: Urgency;
  location: string;
  raw_message: string;
  status: 'open' | 'acknowledged' | 'resolved';
  severity: 'critical' | 'high' | 'medium';
  sla: SLAInfo;
  created_at: string;
}

export interface DashboardSummary {
  open_service_requests: number;
  waiting_approval_count: number;
  today_appointments_count: number;
  total_appointments_count: number;
  open_escalations_count: number;
  sla_at_risk_count: number;
  sla_breached_count: number;
  pending_outbox_count: number;
}

export interface SystemStatus {
  api: {
    status: string;
    version: string;
  };
  database: {
    status: string;
    pool_size: number;
  };
  redis: {
    status: string;
  };
  outbox: {
    pending_count: number;
  };
  integrations: {
    failed_count: number;
  };
}
