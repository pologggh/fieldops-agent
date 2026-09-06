import { zhCN } from './zh-CN/index';
export { branches, teams } from './branchesTeams';
export type { ServiceBranch, ServiceTeam } from './branchesTeams';

export { zhCN };

export type LocaleDict = typeof zhCN;

/**
 * Active locale dictionary (Simplified Chinese by default).
 * Architecture allows adding enUS and switching in the future.
 */
export const t = zhCN;

/**
 * Normalizes backend status phrases (e.g. from customer_portal mapping)
 * to canonical status keys.
 */
export function normalizeCustomerStatus(status?: string | null): string {
  if (!status) return '';
  const s = status.trim().toLowerCase();
  if (s === 'appointment scheduled' || s === 'scheduled' || s === 'appointment_created') return 'scheduled';
  if (s === 'request received' || s === 'received' || s === 'created' || s === 'submitted' || s === 'validated') return 'received';
  if (s === 'more information needed' || s === 'needs_information') return 'needs_information';
  if (s === 'finding a technician' || s === 'matched' || s === 'ready_for_scheduling') return 'matched';
  if (s === 'scheduling your visit' || s === 'waiting_for_approval' || s === 'ready_for_review' || s === 'approved') return 'waiting_for_approval';
  if (s === 'service in progress' || s === 'in_progress') return 'in_progress';
  if (s === 'pending_completion_confirmation') return 'pending_completion_confirmation';
  if (s === 'service completed' || s === 'completed' || s === 'resolved') return 'completed';
  if (s === 'cancelled' || s === 'canceled') return 'cancelled';
  if (s === 'reschedule in progress' || s === 'reschedule_requested') return 'reschedule_requested';
  if (s.includes('reviewing') || s.includes('alternative') || s.includes('conflict') || s.includes('needs_rescheduling')) return 'conflict';
  return s;
}

/**
 * Maps raw backend status enum to localized Chinese text across portals.
 */
export function getStatusText(rawStatus?: string | null): string {
  if (!rawStatus) return '—';
  const normalized = normalizeCustomerStatus(rawStatus);
  const mapping: Record<string, string> = zhCN.status;
  return mapping[normalized] || mapping[rawStatus] || rawStatus.replace(/_/g, ' ');
}

export const getCustomerStatusText = getStatusText;

/**
 * Maps appointment status to Chinese.
 */
export function getAppointmentStatusText(rawStatus?: string | null): string {
  if (!rawStatus) return '—';
  const s = rawStatus.trim().toLowerCase();
  const mapping: Record<string, string> = zhCN.appointmentStatus;
  return mapping[s] || mapping[rawStatus] || getStatusText(rawStatus);
}

/**
 * Maps assignment status to Chinese.
 */
export function getAssignmentStatusText(rawStatus?: string | null): string {
  if (!rawStatus) return '—';
  const s = rawStatus.trim().toLowerCase();
  const mapping: Record<string, string> = zhCN.assignmentStatus;
  return mapping[s] || mapping[rawStatus] || rawStatus;
}

/**
 * Maps SLA adherence status to Chinese.
 */
export function getSLAStatusText(rawStatus?: string | null): string {
  if (!rawStatus) return '—';
  const s = rawStatus.trim().toLowerCase();
  const mapping: Record<string, string> = zhCN.slaStatus;
  return mapping[s] || mapping[rawStatus] || rawStatus;
}

/**
 * Maps user roles to Chinese.
 */
export function getRoleText(role?: string | null): string {
  if (!role) return '—';
  const r = role.trim().toLowerCase();
  const mapping: Record<string, string> = zhCN.roleStatus;
  return mapping[r] || mapping[role] || role;
}

/**
 * Maps escalation severity to Chinese.
 */
export function getSeverityText(severity?: string | null): string {
  if (!severity) return '—';
  const s = severity.trim().toLowerCase();
  const mapping: Record<string, string> = zhCN.severityStatus;
  return mapping[s] || mapping[severity] || severity;
}

/**
 * Maps integration health to Chinese.
 */
export function getIntegrationStatusText(statusStr?: string | null): string {
  if (!statusStr) return '—';
  const s = statusStr.trim().toLowerCase();
  const mapping: Record<string, string> = zhCN.integrationStatus;
  return mapping[s] || mapping[statusStr] || statusStr;
}

/**
 * Maps service types to friendly Chinese names.
 */
export function getServiceTypeText(type?: string | null): string {
  if (!type) return '—';
  const mapping: Record<string, string> = zhCN.serviceType;
  return mapping[type] || type;
}

/**
 * Maps urgency levels to localized Chinese text.
 */
export function getUrgencyText(urgency?: string | null): string {
  if (!urgency) return '—';
  const u = urgency.trim().toLowerCase();
  const mapping: Record<string, string> = zhCN.urgency;
  return mapping[u] || mapping[urgency] || urgency;
}

/**
 * Maps missing field keys to Chinese field names.
 */
export function getMissingFieldText(field?: string | null): string {
  if (!field) return '';
  const mapping: Record<string, string> = zhCN.missingFields;
  return mapping[field] || field.replace(/_/g, ' ');
}

/**
 * Maps HTTP error codes or messages to customer-friendly Chinese.
 */
export function getCustomerErrorMessage(statusOrMessage?: number | string | null): string {
  if (!statusOrMessage) return zhCN.errors.unknown;
  if (typeof statusOrMessage === 'number') {
    const errorMap: Record<number, string> = zhCN.errors;
    return errorMap[statusOrMessage] || zhCN.errors.unknown;
  }
  return statusOrMessage;
}

/**
 * Returns calm status projection for customer presentation.
 */
export function getCustomerCalmStatus(status?: string | null) {
  if (!status) return zhCN.calmStatus.default;
  const normalized = normalizeCustomerStatus(status);
  const map: Record<string, typeof zhCN.calmStatus.default> = zhCN.calmStatus;
  return map[normalized] || map[status] || zhCN.calmStatus.default;
}
