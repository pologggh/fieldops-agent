export interface CustomerUser {
  id: number;
  email: string;
  name: string;
  phone?: string | null;
  address?: string | null;
}

export interface CustomerAuthResponse {
  access_token: string;
  token_type: string;
  customer: CustomerUser;
  success: boolean;
}

export interface CustomerProfile {
  id: number;
  email: string;
  name: string;
  phone: string | null;
  address: string | null;
  created_at: string;
}

export interface CustomerTimelineItem {
  id: string;
  timestamp: string;
  title: string;
  description: string;
}

export interface CustomerAppointmentView {
  id: number;
  service_request_id: number;
  start_time: string;
  end_time: string;
  service_type: string;
  location: string;
  technician_name: string;
  status: string;
  can_cancel: boolean;
  can_reschedule: boolean;
}

export interface CustomerServiceRequestView {
  id: number;
  service_type: string;
  problem_description: string;
  location: string;
  preferred_time: string | null;
  customer_status: string;
  internal_status: string;
  submitted_at: string;
  needs_information: boolean;
  missing_fields: string[];
  can_cancel: boolean;
  can_reschedule: boolean;
  appointment: CustomerAppointmentView | null;
  timeline: CustomerTimelineItem[];
}

export interface CustomerHomeSummary {
  open_requests_count?: number;
  needs_info_count?: number;
  active_requests_count?: number;
  upcoming_appointments_count?: number;
  needs_action_count?: number;
  customer_name?: string;
  upcoming_appointment?: CustomerAppointmentView | null;
  recent_requests?: CustomerServiceRequestView[];
}

export interface CustomerRegisterInput {
  name: string;
  email: string;
  password: string;
  phone?: string;
}

export interface CustomerLoginInput {
  email: string;
  password: string;
}

export interface CustomerProfileUpdateInput {
  name?: string;
  phone?: string;
  address?: string;
}

export interface CustomerServiceRequestCreateInput {
  service_type: string;
  problem_description: string;
  location?: string;
  preferred_time?: string;
}

export interface CustomerServiceRequestSupplementInput {
  location?: string;
  preferred_time?: string;
  additional_details?: string;
}

export interface CustomerServiceRequestCancelInput {
  reason?: string;
}

export interface CustomerRescheduleInput {
  preferred_time: string;
  reason?: string;
}

// =============================================================================
// Conversational Agent Types (Phase 22)
// =============================================================================

export interface ConversationDraft {
  service_type: string;
  urgency: string;
  location: string | null;
  preferred_time: string | null;
  problem_description: string | null;
  required_skills: string[];
  missing_fields: string[];
  is_complete: boolean;
  safety_warning?: string | null;
}

export interface ConversationMessageView {
  id: number;
  conversation_id: number;
  role: 'customer' | 'assistant' | 'system_event';
  content: string;
  client_message_id?: string | null;
  metadata?: Record<string, any> | null;
  created_at: string;
}

export interface ConversationView {
  id: number;
  customer_id: number;
  status: 'active' | 'awaiting_confirmation' | 'submitted' | 'cancelled' | 'closed';
  draft_version: number;
  draft: ConversationDraft;
  messages: ConversationMessageView[];
  submitted_service_request_id?: number | null;
  created_at: string;
  updated_at: string;
  last_message_at?: string | null;
}

export interface ConversationSummaryItem {
  id: number;
  status: string;
  service_type?: string | null;
  draft_preview?: string | null;
  submitted_service_request_id?: number | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationCreateInput {
  initial_message?: string;
  client_message_id?: string;
}

export interface ConversationSendMessageInput {
  content: string;
  client_message_id?: string;
}

export interface ConversationConfirmResponse {
  success: boolean;
  conversation_id: number;
  service_request_id: number;
  status: string;
  message: string;
}

