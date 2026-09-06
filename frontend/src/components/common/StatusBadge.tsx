import React from 'react';
import {
  Clock,
  AlertTriangle,
  AlertOctagon,
  AlertCircle,
  CheckCircle2,
  Calendar,
  PlayCircle,
  XCircle,
  Shield,
  UserCheck,
  Eye,
  RefreshCw,
  Zap,
  Check,
} from 'lucide-react';
import {
  getStatusText,
  getAppointmentStatusText,
  getAssignmentStatusText,
  getSLAStatusText,
  getUrgencyText,
  getRoleText,
  getSeverityText,
  getIntegrationStatusText,
  normalizeCustomerStatus,
} from '../../locales';

export interface StatusBadgeProps {
  type: 'sla' | 'urgency' | 'status' | 'appointment' | 'assignment' | 'role' | 'severity' | 'integration';
  value: string;
  className?: string;
  showIcon?: boolean;
  locale?: 'en' | 'zh'; // Retained for type compatibility, defaults to zh
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  type,
  value,
  className = '',
  showIcon = true,
}) => {
  let bgClass = 'bg-slate-100 text-slate-700 border-slate-200';
  let label = value;
  let icon: React.ReactNode = null;

  if (type === 'sla') {
    const s = (value || '').toLowerCase();
    label = getSLAStatusText(s);
    switch (s) {
      case 'on_track':
        bgClass = 'bg-emerald-50 text-emerald-700 border-emerald-200';
        icon = <CheckCircle2 className="w-3 h-3 text-emerald-600 shrink-0" />;
        break;
      case 'at_risk':
        bgClass = 'bg-amber-50 text-amber-800 border-amber-300 font-medium';
        icon = <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0 animate-pulse" />;
        break;
      case 'breached':
        bgClass = 'bg-rose-50 text-rose-700 border-rose-300 font-semibold';
        icon = <AlertOctagon className="w-3 h-3 text-rose-600 shrink-0" />;
        break;
      case 'completed':
        bgClass = 'bg-slate-100 text-slate-600 border-slate-200';
        icon = <CheckCircle2 className="w-3 h-3 text-slate-500 shrink-0" />;
        break;
      default:
        bgClass = 'bg-slate-100 text-slate-700 border-slate-200';
        icon = <Clock className="w-3 h-3 text-slate-500 shrink-0" />;
    }
  } else if (type === 'urgency') {
    const u = (value || '').toLowerCase();
    label = getUrgencyText(u);
    switch (u) {
      case 'emergency':
        bgClass = 'bg-rose-100 text-rose-800 border-rose-300 font-bold';
        icon = <AlertOctagon className="w-3 h-3 text-rose-700 shrink-0" />;
        break;
      case 'high':
        bgClass = 'bg-amber-100 text-amber-800 border-amber-300 font-medium';
        icon = <AlertTriangle className="w-3 h-3 text-amber-700 shrink-0" />;
        break;
      case 'medium':
        bgClass = 'bg-sky-50 text-sky-700 border-sky-200';
        icon = <Clock className="w-3 h-3 text-sky-600 shrink-0" />;
        break;
      case 'low':
        bgClass = 'bg-slate-100 text-slate-600 border-slate-200';
        icon = <Clock className="w-3 h-3 text-slate-400 shrink-0" />;
        break;
      default:
        bgClass = 'bg-slate-100 text-slate-700 border-slate-200';
        icon = <Clock className="w-3 h-3 text-slate-500 shrink-0" />;
    }
  } else if (type === 'status') {
    const normValue = normalizeCustomerStatus(value);
    label = getStatusText(normValue);
    switch (normValue) {
      case 'waiting_for_approval':
      case 'ready_for_review':
        bgClass = 'bg-purple-50 text-purple-700 border-purple-200 font-medium';
        icon = <Clock className="w-3 h-3 text-purple-600 shrink-0" />;
        break;
      case 'scheduled':
      case 'appointment_created':
        bgClass = 'bg-emerald-50 text-emerald-700 border-emerald-200 font-medium';
        icon = <Calendar className="w-3 h-3 text-emerald-600 shrink-0" />;
        break;
      case 'received':
      case 'validated':
      case 'open':
      case 'created':
      case 'submitted':
        bgClass = 'bg-indigo-50 text-indigo-700 border-indigo-200';
        icon = <Clock className="w-3 h-3 text-indigo-600 shrink-0" />;
        break;
      case 'needs_information':
        bgClass = 'bg-amber-50 text-amber-800 border-amber-300 font-medium';
        icon = <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0" />;
        break;
      case 'matched':
      case 'pending_dispatch':
      case 'dispatching':
        bgClass = 'bg-purple-50 text-purple-700 border-purple-200 font-medium';
        icon = <Clock className="w-3 h-3 text-purple-600 shrink-0" />;
        break;
      case 'in_progress':
        bgClass = 'bg-sky-50 text-sky-700 border-sky-200 font-medium';
        icon = <PlayCircle className="w-3 h-3 text-sky-600 shrink-0" />;
        break;
      case 'pending_completion_confirmation':
        bgClass = 'bg-amber-50 text-amber-800 border-amber-300 font-medium';
        icon = <Check className="w-3 h-3 text-amber-600 shrink-0" />;
        break;
      case 'completed':
      case 'resolved':
        bgClass = 'bg-slate-100 text-slate-700 border-slate-300';
        icon = <CheckCircle2 className="w-3 h-3 text-slate-600 shrink-0" />;
        break;
      case 'approved':
        bgClass = 'bg-sky-50 text-sky-700 border-sky-200';
        icon = <CheckCircle2 className="w-3 h-3 text-sky-600 shrink-0" />;
        break;
      case 'rejected':
        bgClass = 'bg-rose-50 text-rose-700 border-rose-200';
        icon = <XCircle className="w-3 h-3 text-rose-600 shrink-0" />;
        break;
      case 'conflict':
      case 'needs_rescheduling':
        bgClass = 'bg-amber-50 text-amber-800 border-amber-300 font-medium';
        icon = <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0" />;
        break;
      case 'reschedule_requested':
        bgClass = 'bg-amber-50 text-amber-800 border-amber-300 font-medium';
        icon = <RefreshCw className="w-3 h-3 text-amber-600 shrink-0" />;
        break;
      case 'cancelled':
      case 'canceled':
        bgClass = 'bg-slate-100 text-slate-600 border-slate-200';
        icon = <XCircle className="w-3 h-3 text-slate-500 shrink-0" />;
        break;
      case 'escalated':
        bgClass = 'bg-rose-100 text-rose-800 border-rose-300 font-semibold';
        icon = <AlertOctagon className="w-3 h-3 text-rose-600 shrink-0" />;
        break;
      default:
        bgClass = 'bg-slate-100 text-slate-700 border-slate-200';
        icon = <Clock className="w-3 h-3 text-slate-500 shrink-0" />;
    }
  } else if (type === 'appointment') {
    const a = (value || '').toLowerCase();
    label = getAppointmentStatusText(a);
    switch (a) {
      case 'proposed':
      case 'pending':
        bgClass = 'bg-purple-50 text-purple-700 border-purple-200 font-medium';
        icon = <Clock className="w-3 h-3 text-purple-600 shrink-0" />;
        break;
      case 'scheduled':
      case 'confirmed':
        bgClass = 'bg-emerald-50 text-emerald-700 border-emerald-200 font-medium';
        icon = <Calendar className="w-3 h-3 text-emerald-600 shrink-0" />;
        break;
      case 'in_progress':
        bgClass = 'bg-sky-50 text-sky-700 border-sky-200 font-medium';
        icon = <PlayCircle className="w-3 h-3 text-sky-600 shrink-0" />;
        break;
      case 'completed':
        bgClass = 'bg-slate-100 text-slate-700 border-slate-300';
        icon = <CheckCircle2 className="w-3 h-3 text-slate-600 shrink-0" />;
        break;
      case 'reschedule_requested':
        bgClass = 'bg-amber-50 text-amber-800 border-amber-300 font-medium';
        icon = <RefreshCw className="w-3 h-3 text-amber-600 shrink-0" />;
        break;
      case 'cancelled':
      case 'canceled':
        bgClass = 'bg-slate-100 text-slate-600 border-slate-200';
        icon = <XCircle className="w-3 h-3 text-slate-500 shrink-0" />;
        break;
      default:
        bgClass = 'bg-slate-100 text-slate-700 border-slate-200';
        icon = <Calendar className="w-3 h-3 text-slate-500 shrink-0" />;
    }
  } else if (type === 'assignment') {
    const asg = (value || '').toLowerCase();
    label = getAssignmentStatusText(asg);
    switch (asg) {
      case 'pending':
        bgClass = 'bg-purple-50 text-purple-700 border-purple-200 font-medium';
        icon = <Clock className="w-3 h-3 text-purple-600 shrink-0" />;
        break;
      case 'accepted':
        bgClass = 'bg-emerald-50 text-emerald-700 border-emerald-200 font-medium';
        icon = <CheckCircle2 className="w-3 h-3 text-emerald-600 shrink-0" />;
        break;
      case 'rejected':
        bgClass = 'bg-rose-50 text-rose-700 border-rose-200';
        icon = <XCircle className="w-3 h-3 text-rose-600 shrink-0" />;
        break;
      case 'superseded':
        bgClass = 'bg-amber-50 text-amber-800 border-amber-300';
        icon = <RefreshCw className="w-3 h-3 text-amber-600 shrink-0" />;
        break;
      case 'completed':
        bgClass = 'bg-slate-100 text-slate-700 border-slate-300';
        icon = <CheckCircle2 className="w-3 h-3 text-slate-600 shrink-0" />;
        break;
      case 'cancelled':
      case 'canceled':
        bgClass = 'bg-slate-100 text-slate-600 border-slate-200';
        icon = <XCircle className="w-3 h-3 text-slate-500 shrink-0" />;
        break;
      default:
        bgClass = 'bg-slate-100 text-slate-700 border-slate-200';
        icon = <Clock className="w-3 h-3 text-slate-500 shrink-0" />;
    }
  } else if (type === 'role') {
    const r = (value || '').toLowerCase();
    label = getRoleText(r);
    switch (r) {
      case 'admin':
        bgClass = 'bg-rose-50 text-rose-700 border-rose-200 font-semibold';
        icon = <Shield className="w-3 h-3 text-rose-600 shrink-0" />;
        break;
      case 'operator':
        bgClass = 'bg-indigo-50 text-indigo-700 border-indigo-200 font-medium';
        icon = <UserCheck className="w-3 h-3 text-indigo-600 shrink-0" />;
        break;
      case 'viewer':
        bgClass = 'bg-slate-100 text-slate-600 border-slate-200';
        icon = <Eye className="w-3 h-3 text-slate-500 shrink-0" />;
        break;
      case 'customer':
        bgClass = 'bg-emerald-50 text-emerald-700 border-emerald-200';
        icon = <UserCheck className="w-3 h-3 text-emerald-600 shrink-0" />;
        break;
      default:
        bgClass = 'bg-slate-100 text-slate-700 border-slate-200';
    }
  } else if (type === 'severity') {
    const sev = (value || '').toLowerCase();
    label = getSeverityText(sev);
    switch (sev) {
      case 'critical':
        bgClass = 'bg-rose-100 text-rose-800 border-rose-300 font-bold';
        icon = <AlertOctagon className="w-3 h-3 text-rose-700 shrink-0" />;
        break;
      case 'high':
        bgClass = 'bg-amber-100 text-amber-800 border-amber-300 font-medium';
        icon = <AlertTriangle className="w-3 h-3 text-amber-700 shrink-0" />;
        break;
      case 'medium':
        bgClass = 'bg-sky-50 text-sky-700 border-sky-200';
        icon = <Clock className="w-3 h-3 text-sky-600 shrink-0" />;
        break;
      case 'low':
        bgClass = 'bg-slate-100 text-slate-600 border-slate-200';
        icon = <Clock className="w-3 h-3 text-slate-400 shrink-0" />;
        break;
      default:
        bgClass = 'bg-slate-100 text-slate-700 border-slate-200';
    }
  } else if (type === 'integration') {
    const itg = (value || '').toLowerCase();
    label = getIntegrationStatusText(itg);
    switch (itg) {
      case 'healthy':
      case 'running':
      case 'synced':
      case 'active':
        bgClass = 'bg-emerald-50 text-emerald-700 border-emerald-200';
        icon = <CheckCircle2 className="w-3 h-3 text-emerald-600 shrink-0" />;
        break;
      case 'warning':
      case 'at_risk':
      case 'pending':
        bgClass = 'bg-amber-50 text-amber-800 border-amber-300 font-medium';
        icon = <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0" />;
        break;
      case 'failed':
      case 'error':
        bgClass = 'bg-rose-50 text-rose-700 border-rose-200 font-medium';
        icon = <XCircle className="w-3 h-3 text-rose-600 shrink-0" />;
        break;
      case 'disabled':
      case 'inactive':
      case 'cancelled':
        bgClass = 'bg-slate-100 text-slate-600 border-slate-200';
        icon = <Clock className="w-3 h-3 text-slate-400 shrink-0" />;
        break;
      default:
        bgClass = 'bg-slate-100 text-slate-700 border-slate-200';
    }
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border transition-colors shadow-2xs whitespace-nowrap ${bgClass} ${className}`}
    >
      {showIcon && icon}
      <span>{label}</span>
    </span>
  );
};
