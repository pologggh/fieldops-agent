import { apiClient } from './client';
import {
  InternalUser,
  InternalUserCreateInput,
  InternalUserUpdateInput,
  TechnicianAdmin,
  TechnicianCreateInput,
  TechnicianUpdateInput,
  DispatchPolicy,
  DispatchPolicyCreateInput,
  SLAPolicy,
  SLAPolicyCreateInput,
  IntegrationSummary,
  IntegrationFailure,
  AuditLogEntry,
  SystemSummary,
} from '../types/admin';

// ============================================================================
// 1. Internal User Management
// ============================================================================

export async function getInternalUsers(): Promise<InternalUser[]> {
  return apiClient<InternalUser[]>('/admin/users');
}

export async function createInternalUser(data: InternalUserCreateInput): Promise<InternalUser> {
  return apiClient<InternalUser>('/admin/users', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getInternalUser(id: number): Promise<InternalUser> {
  return apiClient<InternalUser>(`/admin/users/${id}`);
}

export async function updateInternalUser(id: number, data: InternalUserUpdateInput): Promise<InternalUser> {
  return apiClient<InternalUser>(`/admin/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function activateInternalUser(id: number): Promise<InternalUser> {
  return apiClient<InternalUser>(`/admin/users/${id}/activate`, {
    method: 'POST',
  });
}

export async function deactivateInternalUser(id: number): Promise<InternalUser> {
  return apiClient<InternalUser>(`/admin/users/${id}/deactivate`, {
    method: 'POST',
  });
}

export async function changeUserRole(id: number, role: string): Promise<InternalUser> {
  return apiClient<InternalUser>(`/admin/users/${id}/role`, {
    method: 'POST',
    body: JSON.stringify({ role }),
  });
}

// ============================================================================
// 2. Technician Management
// ============================================================================

export async function getAdminTechnicians(): Promise<TechnicianAdmin[]> {
  return apiClient<TechnicianAdmin[]>('/admin/technicians');
}

export async function createTechnician(data: TechnicianCreateInput): Promise<TechnicianAdmin> {
  return apiClient<TechnicianAdmin>('/admin/technicians', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getAdminTechnician(id: number): Promise<TechnicianAdmin> {
  return apiClient<TechnicianAdmin>(`/admin/technicians/${id}`);
}

export async function updateTechnician(id: number, data: TechnicianUpdateInput): Promise<TechnicianAdmin> {
  return apiClient<TechnicianAdmin>(`/admin/technicians/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function activateTechnician(id: number): Promise<TechnicianAdmin> {
  return apiClient<TechnicianAdmin>(`/admin/technicians/${id}/activate`, {
    method: 'POST',
  });
}

export async function deactivateTechnician(id: number): Promise<TechnicianAdmin> {
  return apiClient<TechnicianAdmin>(`/admin/technicians/${id}/deactivate`, {
    method: 'POST',
  });
}

// ============================================================================
// 3. Dispatch Policy Management
// ============================================================================

export async function getDispatchPolicies(): Promise<DispatchPolicy[]> {
  return apiClient<DispatchPolicy[]>('/admin/policies/dispatch');
}

export async function createDispatchPolicy(data: DispatchPolicyCreateInput): Promise<DispatchPolicy> {
  return apiClient<DispatchPolicy>('/admin/policies/dispatch', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function activateDispatchPolicy(version: number): Promise<DispatchPolicy> {
  return apiClient<DispatchPolicy>(`/admin/policies/dispatch/${version}/activate`, {
    method: 'POST',
  });
}

// ============================================================================
// 4. SLA Policy Management
// ============================================================================

export async function getSLAPolicies(): Promise<SLAPolicy[]> {
  return apiClient<SLAPolicy[]>('/admin/policies/sla');
}

export async function createSLAPolicy(data: SLAPolicyCreateInput): Promise<SLAPolicy> {
  return apiClient<SLAPolicy>('/admin/policies/sla', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function activateSLAPolicy(version: number): Promise<SLAPolicy> {
  return apiClient<SLAPolicy>(`/admin/policies/sla/${version}/activate`, {
    method: 'POST',
  });
}

// ============================================================================
// 5. Integration Status
// ============================================================================

export async function getIntegrationSummary(): Promise<IntegrationSummary> {
  return apiClient<IntegrationSummary>('/admin/integrations/summary');
}

export async function getIntegrationFailures(provider?: string, limit = 50): Promise<IntegrationFailure[]> {
  const query = new URLSearchParams();
  if (provider) query.set('provider', provider);
  query.set('limit', String(limit));
  const queryString = query.toString();
  return apiClient<IntegrationFailure[]>(`/admin/integrations/failures${queryString ? `?${queryString}` : ''}`);
}

// ============================================================================
// 6. Audit Review
// ============================================================================

export async function getAuditLogs(params?: {
  entity_type?: string;
  entity_id?: string;
  action?: string;
  limit?: number;
}): Promise<AuditLogEntry[]> {
  const query = new URLSearchParams();
  if (params?.entity_type) query.set('entity_type', params.entity_type);
  if (params?.entity_id) query.set('entity_id', params.entity_id);
  if (params?.action) query.set('action', params.action);
  if (params?.limit) query.set('limit', String(params.limit));
  const queryString = query.toString();
  return apiClient<AuditLogEntry[]>(`/admin/audit${queryString ? `?${queryString}` : ''}`);
}

// ============================================================================
// 7. System Health & Telemetry
// ============================================================================

export async function getSystemSummary(): Promise<SystemSummary> {
  return apiClient<SystemSummary>('/admin/system/summary');
}
