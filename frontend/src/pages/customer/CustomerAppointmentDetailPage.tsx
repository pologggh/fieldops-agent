import React, { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as customerApi from '../../api/customerApi';
import {
  ArrowLeft,
  Clock,
  MapPin,
  CheckCircle2,
  XCircle,
  FileText,
  AlertTriangle,
  User,
  Calendar,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';
import { StatusBadge, Button, Dialog } from '../../components/ui';
import { formatDateTimeZh, formatTimeRangeZh, formatTimeZh } from '../../utils/dateTime';
import { t, getServiceTypeText } from '../../locales';

export const CustomerAppointmentDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const apptId = parseInt(id || '0', 10);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: appt, isLoading, error } = useQuery({
    queryKey: ['customer-appointment', apptId],
    queryFn: () => customerApi.fetchCustomerAppointment(apptId),
    enabled: !!apptId,
  });

  const cancelMutation = useMutation({
    mutationFn: (reason?: string) => customerApi.cancelCustomerAppointment(apptId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer-appointment', apptId] });
      queryClient.invalidateQueries({ queryKey: ['customer-appointments'] });
      queryClient.invalidateQueries({ queryKey: ['customer-summary'] });
      setShowCancelModal(false);
      setActionError(null);
    },
    onError: (err: any) => {
      setActionError(err.message || '取消预约失败，请重试。');
    },
  });

  const handleCancelSubmit = () => {
    cancelMutation.mutate(cancelReason.trim() || undefined);
  };

  const getApptDateBlock = (startTimeStr?: string) => {
    if (!startTimeStr) return { month: '预约', day: '--', weekday: '待定' };
    const date = new Date(startTimeStr);
    if (isNaN(date.getTime())) return { month: '预约', day: '--', weekday: '待确认' };
    const month = `${date.getMonth() + 1}月`;
    const day = String(date.getDate()).padStart(2, '0');
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    const weekday = weekdays[date.getDay()];
    return { month, day, weekday };
  };

  if (isLoading) {
    return <div className="py-16 text-center text-xs text-slate-400">{t.common.loading}</div>;
  }

  if (error || !appt) {
    return (
      <div className="bg-white p-8 rounded-2xl border border-slate-200 text-center max-w-lg mx-auto my-12">
        <h2 className="text-base font-bold text-slate-900">{t.appointmentDetail.notFoundTitle}</h2>
        <p className="mt-1 text-xs text-slate-500">
          {t.appointmentDetail.notFoundDesc}
        </p>
        <Link
          to="/customer/appointments"
          className="mt-4 inline-flex items-center text-xs font-semibold text-emerald-600 hover:underline"
        >
          <ArrowLeft className="w-3.5 h-3.5 mr-1" /> {t.appointmentDetail.backToAppointments}
        </Link>
      </div>
    );
  }

  const dateBlock = getApptDateBlock(appt.start_time);

  return (
    <div className="max-w-2xl mx-auto space-y-6 pb-12">
      {/* Back link */}
      <div>
        <Link
          to="/customer/appointments"
          className="inline-flex items-center text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors group mb-3"
        >
          <ArrowLeft className="w-3.5 h-3.5 mr-1 group-hover:-translate-x-0.5 transition-transform" />
          {t.appointmentDetail.backToAppointments}
        </Link>

        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-medium text-slate-400">
                {t.appointmentDetail.visitPrefix.replace('{id}', String(appt.id))}
              </span>
              <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
                {getServiceTypeText(appt.service_type)}
              </h1>
            </div>
          </div>

          {appt.can_cancel && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowCancelModal(true)}
              leftIcon={<XCircle className="w-3.5 h-3.5 text-rose-600" />}
              className="border-rose-200 text-rose-700 hover:bg-rose-50"
            >
              {t.appointmentDetail.cancelVisitBtn}
            </Button>
          )}
        </div>
      </div>

      {actionError && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Appointment Information Card */}
      <div className="bg-white p-6 sm:p-8 rounded-3xl border border-slate-200/80 shadow-sm space-y-6">
        {/* Status Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div>
            <div className="text-xs text-slate-400 font-medium">{t.appointmentDetail.statusLabel}</div>
            <div className="mt-1">
              <StatusBadge type="status" value={appt.status} locale="zh" />
            </div>
          </div>
          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-700" />
            {t.appointmentDetail.confirmedVisit}
          </span>
        </div>

        {/* Date & Time Showcase */}
        <div className="flex items-start gap-4 p-5 rounded-2xl bg-gradient-to-br from-emerald-50/70 to-teal-50/40 border border-emerald-200/70">
          <div className="shrink-0 text-center bg-white rounded-xl px-3.5 py-2.5 border border-emerald-200/80 shadow-xs">
            <div className="text-[10px] font-bold text-emerald-800 uppercase tracking-wider">
              {dateBlock.month}
            </div>
            <div className="text-3xl font-black text-slate-900 leading-none my-0.5">
              {dateBlock.day}
            </div>
            <div className="text-[10px] font-medium text-slate-500">
              {dateBlock.weekday}
            </div>
          </div>

          <div className="space-y-1 min-w-0 flex-1">
            <div className="text-xs font-semibold text-emerald-800">
              {t.appointmentDetail.scheduledArrivalWindow}
            </div>
            <div className="text-base sm:text-lg font-bold text-slate-900 font-mono tracking-tight">
              {formatTimeRangeZh(appt.start_time, appt.end_time)}
            </div>
            <div className="text-xs text-slate-500 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              <span>{t.appointmentDetail.expectedDuration.replace('{time}', formatTimeZh(appt.end_time))}</span>
            </div>
          </div>
        </div>

        {/* Specialist & Location Details */}
        <div className="space-y-4 text-xs pt-1">
          <div className="flex items-start gap-3 p-3.5 rounded-xl bg-slate-50 border border-slate-100">
            <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-800 flex items-center justify-center shrink-0">
              <User className="w-4 h-4" />
            </div>
            <div>
              <span className="font-semibold text-slate-700 block">{t.appointmentDetail.certifiedSpecialist}</span>
              <span className="text-slate-900 text-sm font-bold block mt-0.5">{appt.technician_name}</span>
              <span className="text-slate-400 text-[11px] block mt-0.5">持证技术工程师 · 携带标准维保工具与防护装备</span>
            </div>
          </div>

          <div className="flex items-start gap-3 p-3.5 rounded-xl bg-slate-50 border border-slate-100">
            <div className="w-8 h-8 rounded-lg bg-slate-200/80 text-slate-700 flex items-center justify-center shrink-0">
              <MapPin className="w-4 h-4" />
            </div>
            <div>
              <span className="font-semibold text-slate-700 block">{t.appointmentDetail.serviceLocation}</span>
              <span className="text-slate-800 text-xs font-medium block mt-0.5">{appt.location || t.appointmentDetail.onSiteDefault}</span>
            </div>
          </div>

          <div className="pt-2">
            <Link
              to={`/customer/requests/${appt.service_request_id}`}
              className="p-3.5 rounded-xl border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/30 transition-all flex items-center justify-between group"
            >
              <div className="flex items-center gap-2.5">
                <FileText className="w-4 h-4 text-slate-400 group-hover:text-emerald-600 transition-colors" />
                <span className="font-medium text-slate-700 text-xs">
                  {t.appointmentDetail.viewAssociatedTicket.replace('{id}', String(appt.service_request_id))}
                </span>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-emerald-600 group-hover:translate-x-0.5 transition-all" />
            </Link>
          </div>
        </div>
      </div>

      {/* Cancel Dialog */}
      <Dialog
        isOpen={showCancelModal}
        onClose={() => setShowCancelModal(false)}
        title={t.appointmentDetail.cancelModal.title}
        variant="danger"
        confirmLabel={cancelMutation.isPending ? t.appointmentDetail.cancelModal.cancellingBtn : t.appointmentDetail.cancelModal.confirmBtn}
        cancelLabel={t.appointmentDetail.cancelModal.keepBtn}
        isLoading={cancelMutation.isPending}
        onConfirm={handleCancelSubmit}
      >
        <div className="space-y-3 text-xs text-slate-600">
          <p>
            {t.appointmentDetail.cancelModal.confirmText.replace('{id}', String(appt.id))}
          </p>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              {t.appointmentDetail.cancelModal.reasonLabel}
            </label>
            <textarea
              rows={2}
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder={t.appointmentDetail.cancelModal.reasonPlaceholder}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-rose-500 focus:outline-none"
            />
          </div>
        </div>
      </Dialog>
    </div>
  );
};
