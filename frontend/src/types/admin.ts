export interface InternalUser {
  id: number;
  email: string;
  name: string;
  role: 'admin' | 'operator' | 'viewer';
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

export interface InternalUserCreateInput {
  email: string;
  name: string;
  role: 'admin' | 'operator' | 'viewer';
  password: string;
}

export interface InternalUserUpdateInput {
  name?: string;
}

export interface TechnicianAdmin {
  id: number;
  name: string;
  service_area: string;
  status: string;
  skills: string[];
  max_daily_work_minutes: number;
  max_daily_jobs: number;
  is_available_for_emergency: boolean;
  current_active_jobs: number;
}

export interface TechnicianCreateInput {
  name: string;
  service_area: string;
  skills: string[];
  max_daily_work_minutes: number;
  max_daily_jobs: number;
  is_available_for_emergency: boolean;
}

export interface TechnicianUpdateInput {
  name?: string;
  service_area?: string;
  skills?: string[];
  max_daily_work_minutes?: number;
  max_daily_jobs?: number;
  is_available_for_emergency?: boolean;
}

export interface DispatchWeights {
  workload_weight: number;
  capacity_weight: number;
  sla_weight: number;
  travel_weight: number;
  overtime_penalty: number;
}

export interface DispatchPolicy {
  id: number;
  version: number;
  is_active: boolean;
  weights: DispatchWeights;
  description: string | null;
  created_by: string;
  created_at: string;
}

export interface DispatchPolicyCreateInput {
  weights: DispatchWeights;
  description?: string;
  set_active?: boolean;
}

export interface SLATargetTier {
  response_minutes: number;
  assignment_minutes: number;
  service_start_minutes: number;
  at_risk_threshold_minutes: number;
}

export interface SLAPolicy {
  id: number;
  version: number;
  is_active: boolean;
  targets: Record<string, SLATargetTier>;
  description: string | null;
  created_by: string;
  created_at: string;
}

export interface SLAPolicyCreateInput {
  targets: Record<string, SLATargetTier>;
  description?: string;
  set_active?: boolean;
}

export interface IntegrationProvider {
  provider: string;
  type: string;
  is_mock: boolean;
  badge: string;
  status: string;
  success_count: number;
  failure_count: number;
  last_sync: string | null;
}

export interface IntegrationSummary {
  providers: IntegrationProvider[];
  total_synced: number;
  total_failed: number;
}

export interface IntegrationFailure {
  id: number;
  provider: string;
  resource_type?: string;
  local_resource_id?: number;
  appointment_id?: number;
  attempt_count: number;
  last_error: string | null;
  last_error_summary?: string | null;
  updated_at: string;
}

export interface AuditLogEntry {
  id: number;
  entity_type: string;
  entity_id: string;
  action: string;
  summary?: string;
  actor?: string;
  actor_type?: string;
  details: Record<string, any>;
  timestamp: string;
}

export interface SystemSummary {
  health_status: string;
  readiness_status: string;
  database: string;
  redis: string;
  active_internal_users: number;
  active_technicians: number;
  open_service_requests: number;
  pending_outbox_events: number;
  llm_config: {
    provider: string;
    model: string;
    configured: boolean;
  };
}
