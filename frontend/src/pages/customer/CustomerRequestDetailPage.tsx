import React, { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as customerApi from '../../api/customerApi';
import {
  ArrowLeft,
  AlertTriangle,
  Calendar,
  CheckCircle2,
  Clock,
  MapPin,
  XCircle,
  FileText,
  Send,
  CalendarClock,
  Wrench,
  User,
  ShieldCheck,
  ChevronRight,
  Sparkles,
  Info,
  Check,
} from 'lucide-react';
import {
  Dialog,
  Button,
  StatusBadge,
  DetailSkeleton,
  ErrorState,
} from '../../components/ui';
import { formatDateTimeZh, formatTimeRangeZh } from '../../utils/dateTime';
import { t, getServiceTypeText, getCustomerCalmStatus } from '../../locales';

export const CustomerRequestDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const requestId = parseInt(id || '0', 10);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Supplement Form State
  const [suppLocation, setSuppLocation] = useState('');
  const [suppTime, setSuppTime] = useState('');
  const [suppDetails, setSuppDetails] = useState('');

  // Cancel Modal State
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelReason, setCancelReason] = useState('');

  // Reschedule Modal State
  const [showRescheduleModal, setShowRescheduleModal] = useState(false);
  const [rescheduleTime, setRescheduleTime] = useState('');
  const [rescheduleReason, setRescheduleReason] = useState('');

  const [actionError, setActionError] = useState<string | null>(null);

  const { data: request, isLoading, error, refetch } = useQuery({
    queryKey: ['customer-request', requestId],
    queryFn: () => customerApi.fetchCustomerRequest(requestId),
    enabled: !!requestId,
  });

  // Supplement Mutation
  const supplementMutation = useMutation({
    mutationFn: (data: { location?: string; preferred_time?: string; additional_details?: string }) =>
      customerApi.supplementCustomerRequest(requestId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer-request', requestId] });
      queryClient.invalidateQueries({ queryKey: ['customer-requests'] });
      queryClient.invalidateQueries({ queryKey: ['customer-summary'] });
      setSuppLocation('');
      setSuppTime('');
      setSuppDetails('');
      setActionError(null);
    },
    onError: (err: any) => {
      setActionError(err.message || '提交补充信息失败，请重试。');
    },
  });

  // Cancel Mutation
  const cancelMutation = useMutation({
    mutationFn: (reason?: string) =>
      customerApi.cancelCustomerRequest(requestId, { reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer-request', requestId] });
      queryClient.invalidateQueries({ queryKey: ['customer-requests'] });
      queryClient.invalidateQueries({ queryKey: ['customer-summary'] });
      setShowCancelModal(false);
      setActionError(null);
    },
    onError: (err: any) => {
      setActionError(err.message || '取消服务单失败，请重试。');
    },
  });

  // Reschedule Mutation
  const rescheduleMutation = useMutation({
    mutationFn: (data: { preferred_time: string; reason?: string }) =>
      customerApi.rescheduleCustomerRequest(requestId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer-request', requestId] });
      queryClient.invalidateQueries({ queryKey: ['customer-requests'] });
      setShowRescheduleModal(false);
      setActionError(null);
    },
    onError: (err: any) => {
      setActionError(err.message || '申请改期失败，请重试。');
    },
  });

  const handleSupplementSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    supplementMutation.mutate({
      location: suppLocation.trim() || undefined,
      preferred_time: suppTime.trim() || undefined,
      additional_details: suppDetails.trim() || undefined,
    });
  };

  const handleCancelSubmit = () => {
    cancelMutation.mutate(cancelReason.trim() || undefined);
  };

  const handleRescheduleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!rescheduleTime.trim()) return;
    rescheduleMutation.mutate({
      preferred_time: rescheduleTime.trim(),
      reason: rescheduleReason.trim() || undefined,
    });
  };

  if (isLoading) {
    return <DetailSkeleton />;
  }

  if (error || !request) {
    return (
      <ErrorState
        title={t.requestDetail.notFoundTitle}
        message={(error as any)?.message || t.requestDetail.notFoundMessage}
        onRetry={() => refetch()}
      />
    );
  }

  const reqStatus = request.customer_status || request.internal_status;
  const isTerminal = ['completed', 'cancelled', 'rejected'].includes(reqStatus);
  const isScheduled = reqStatus === 'scheduled';
  const isRescheduling = reqStatus === 'reschedule_requested';
  const calmStatus = getCustomerCalmStatus(reqStatus);

  // Date block formatting for appointment
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

  const getDisplayServiceTitle = (type?: string) => {
    const text = getServiceTypeText(type);
    if (text.endsWith('维修') || text.endsWith('维护') || text.endsWith('服务') || text.endsWith('巡检')) {
      return text;
    }
    return `${text} 维修服务`;
  };

  const formatTimelineTitle = (title: string) => {
    if (title === 'Request Received') return '服务需求已受理';
    if (title === 'Appointment Confirmed') return '上门服务预约已确认';
    if (title === 'More Information Needed') return '需补充现场信息';
    if (title === 'Technician Dispatched') return '工程师已接单安排';
    if (title === 'Service Completed') return '维修作业已完工';
    return title;
  };

  const formatTimelineDesc = (desc: string) => {
    if (desc.includes('was received')) return '系统已收到并受理您的报修需求，已进入调度流程。';
    if (desc.includes('technician has been scheduled')) return '已为您锁定专属上门服务工程师及到达时间段。';
    return desc;
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      {/* 1. Back Navigation & Header */}
      <div className="space-y-3">
        <Link
          to="/customer/requests"
          className="inline-flex items-center text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors group"
        >
          <ArrowLeft className="w-3.5 h-3.5 mr-1 group-hover:-translate-x-0.5 transition-transform" />
          {t.requestDetail.backToRequests}
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                {getDisplayServiceTitle(request.service_type)} #{request.id}
              </h1>
              <StatusBadge type="status" value={reqStatus} locale="zh" />
            </div>
            <p className="text-xs text-slate-500 flex items-center gap-2">
              <span className="font-mono font-medium text-slate-600">工单 #{request.id}</span>
              <span>•</span>
              <span>{t.requestDetail.placedOn.replace('{time}', formatDateTimeZh(request.submitted_at)).replace('{id}', String(request.id))}</span>
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            {!isTerminal && (
              <>
                {isScheduled && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowRescheduleModal(true)}
                    leftIcon={<CalendarClock className="w-3.5 h-3.5" />}
                  >
                    {t.requestDetail.rescheduleBtn}
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowCancelModal(true)}
                  leftIcon={<XCircle className="w-3.5 h-3.5 text-rose-600" />}
                  className="border-rose-200 text-rose-700 hover:bg-rose-50"
                >
                  {t.requestDetail.cancelBtn}
                </Button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Global Error Banner */}
      {actionError && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Rescheduling In-Progress Callout */}
      {isRescheduling && (
        <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start gap-3 shadow-xs">
          <CalendarClock className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <div className="font-bold text-sm">{t.requestDetail.rescheduleInProgressTitle}</div>
            <p className="mt-0.5 leading-relaxed">
              {t.requestDetail.rescheduleInProgressDesc}
            </p>
          </div>
        </div>
      )}

      {/* 2. Calm Status Projection & Next Step Banner */}
      <div className={`p-4 sm:p-5 rounded-2xl border ${calmStatus.color} shadow-xs flex items-start gap-3.5`}>
        <div className="w-8 h-8 rounded-xl bg-white/80 border border-current/20 flex items-center justify-center shrink-0 shadow-xs">
          <Info className="w-4 h-4" />
        </div>
        <div className="space-y-1 min-w-0 flex-1">
          <div className="font-bold text-sm sm:text-base flex items-center gap-2">
            <span>当前进展：{calmStatus.title}</span>
          </div>
          <p className="text-xs sm:text-sm leading-relaxed opacity-90">
            {calmStatus.desc}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Details, Appointment & Supplement Form */}
        <div className="lg:col-span-2 space-y-6">
          {/* Main Problem Card */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-sm space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <FileText className="w-4 h-4 text-indigo-600" />
                {t.requestDetail.problemSummaryTitle}
              </h3>
              <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2.5 py-0.5 rounded-full">
                {getServiceTypeText(request.service_type)}
              </span>
            </div>

            <div className="p-4 bg-slate-50/80 border border-slate-100 rounded-xl text-xs sm:text-sm text-slate-800 leading-relaxed font-sans whitespace-pre-wrap">
              {request.problem_description || t.requestDetail.noDescription}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs pt-3 border-t border-slate-100">
              <div className="flex items-start gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-slate-100 text-slate-500 flex items-center justify-center shrink-0 mt-0.5">
                  <MapPin className="w-3.5 h-3.5" />
                </div>
                <div>
                  <span className="font-semibold text-slate-700 block">{t.requestDetail.serviceLocation}</span>
                  <span className="text-slate-600 mt-0.5 block">{request.location || t.requestDetail.pendingLocation}</span>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-slate-100 text-slate-500 flex items-center justify-center shrink-0 mt-0.5">
                  <Clock className="w-3.5 h-3.5" />
                </div>
                <div>
                  <span className="font-semibold text-slate-700 block">{t.requestDetail.preferredTime}</span>
                  <span className="text-slate-600 mt-0.5 block">{request.preferred_time || t.requestDetail.anytimeAvailable}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Confirmed Appointment Information Card */}
          {request.appointment && (
            <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-sm space-y-4">
              <div className="flex justify-between items-center pb-3 border-b border-slate-100">
                <div className="flex items-center space-x-2">
                  <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                    <Calendar className="w-4 h-4" />
                  </div>
                  <h3 className="text-sm font-bold text-slate-900">{t.requestDetail.confirmedAppointmentTitle}</h3>
                </div>
                <StatusBadge type="status" value={request.appointment.status} locale="zh" />
              </div>

              <div className="flex items-start gap-4 p-4 rounded-2xl bg-gradient-to-br from-emerald-50/70 to-teal-50/40 border border-emerald-200/70">
                {/* Large Date Badge */}
                {(() => {
                  const dateBlock = getApptDateBlock(request.appointment.start_time);
                  return (
                    <div className="shrink-0 text-center bg-white rounded-xl px-3 py-2 border border-emerald-200/80 shadow-xs">
                      <div className="text-[10px] font-bold text-emerald-800 uppercase tracking-wider">
                        {dateBlock.month}
                      </div>
                      <div className="text-2xl font-black text-slate-900 leading-none my-0.5">
                        {dateBlock.day}
                      </div>
                      <div className="text-[10px] font-medium text-slate-500">
                        {dateBlock.weekday}
                      </div>
                    </div>
                  );
                })()}

                {/* Visit Details */}
                <div className="space-y-1.5 min-w-0 flex-1">
                  <div className="text-xs font-semibold text-emerald-800">
                    {t.requestDetail.scheduledWindow}
                  </div>
                  <div className="text-sm font-bold text-slate-900 font-mono tracking-tight">
                    {formatTimeRangeZh(request.appointment.start_time, request.appointment.end_time)}
                  </div>
                  <div className="text-xs text-slate-600 flex items-center gap-1.5 pt-0.5">
                    <User className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    <span className="truncate">
                      {t.requestDetail.assignedSpecialist}：<strong>{request.appointment.technician_name}</strong>
                    </span>
                  </div>
                </div>
              </div>

              <div className="pt-2 flex justify-end">
                <Link
                  to={`/customer/appointments/${request.appointment.id}`}
                  className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 inline-flex items-center gap-1 group"
                >
                  <span>{t.requestDetail.viewFullAppointment}</span>
                  <ChevronRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                </Link>
              </div>
            </div>
          )}

          {/* Information Supplement Form if Missing Fields */}
          {request.missing_fields && request.missing_fields.length > 0 && !isTerminal && (
            <div className="bg-amber-50/40 p-6 rounded-2xl border border-amber-200 shadow-sm space-y-4">
              <div className="flex items-center space-x-2 text-amber-900">
                <div className="w-7 h-7 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center">
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-bold">{t.requestDetail.additionalDetailsTitle}</h3>
              </div>
              <p className="text-xs text-slate-600">
                {t.requestDetail.additionalDetailsSubtitle}
              </p>

              <form onSubmit={handleSupplementSubmit} className="space-y-3 pt-1">
                {request.missing_fields.includes('location') && (
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      {t.requestDetail.serviceAddressLabel}
                    </label>
                    <input
                      type="text"
                      value={suppLocation}
                      onChange={(e) => setSuppLocation(e.target.value)}
                      placeholder={t.requestDetail.addressPlaceholder}
                      className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-xs text-slate-900 bg-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 focus:outline-none shadow-xs"
                    />
                  </div>
                )}

                {request.missing_fields.includes('preferred_time') && (
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      {t.requestDetail.preferredTimeLabel}
                    </label>
                    <input
                      type="text"
                      value={suppTime}
                      onChange={(e) => setSuppTime(e.target.value)}
                      placeholder={t.requestDetail.preferredTimePlaceholder}
                      className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-xs text-slate-900 bg-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 focus:outline-none shadow-xs"
                    />
                  </div>
                )}

                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={supplementMutation.isPending}
                  leftIcon={<Send className="w-3.5 h-3.5" />}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium"
                >
                  {t.requestDetail.submitDetailsBtn}
                </Button>
              </form>
            </div>
          )}
        </div>

        {/* Right Column: Service Progress Milestone Timeline */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-sm h-fit space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Clock className="w-4 h-4 text-slate-500" />
              {t.requestDetail.serviceProgressTitle}
            </h3>
            <span className="text-[11px] font-mono text-slate-400">
              {request.timeline.length} 条记录
            </span>
          </div>

          <div className="space-y-6 relative before:absolute before:inset-0 before:left-3.5 before:w-0.5 before:bg-slate-100">
            {request.timeline.map((item, idx) => (
              <div key={item.id} className="relative flex items-start space-x-3.5 group">
                <div className="w-7 h-7 rounded-full bg-indigo-600 text-white flex items-center justify-center shrink-0 text-xs font-bold z-10 ring-4 ring-white shadow-xs">
                  {idx + 1}
                </div>
                <div className="space-y-1 flex-1 min-w-0">
                  <div className="text-xs font-bold text-slate-800 leading-tight">
                    {formatTimelineTitle(item.title)}
                  </div>
                  <p className="text-[11px] text-slate-500 leading-relaxed">
                    {formatTimelineDesc(item.description)}
                  </p>
                  <div className="text-[10px] text-slate-400 font-mono pt-0.5">
                    {formatDateTimeZh(item.timestamp)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Cancel Dialog */}
      <Dialog
        isOpen={showCancelModal}
        onClose={() => setShowCancelModal(false)}
        title={t.requestDetail.cancelModal.title}
        variant="danger"
        confirmLabel={cancelMutation.isPending ? t.requestDetail.cancelModal.cancellingBtn : t.requestDetail.cancelModal.confirmBtn}
        cancelLabel={t.requestDetail.cancelModal.keepBtn}
        isLoading={cancelMutation.isPending}
        onConfirm={handleCancelSubmit}
      >
        <div className="space-y-3 text-xs text-slate-600">
          <p>
            {t.requestDetail.cancelModal.confirmText.replace('{id}', String(request.id))}
          </p>
          {request.appointment && (
            <div className="p-3 bg-rose-50 rounded-xl border border-rose-200 text-rose-800 space-y-1">
              <div className="font-bold">{t.requestDetail.cancelModal.visitImpactTitle}</div>
              <div>
                {t.requestDetail.cancelModal.visitImpactDesc
                  .replace('{time}', formatDateTimeZh(request.appointment.start_time))
                  .replace('{technician}', request.appointment.technician_name)}
              </div>
            </div>
          )}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              {t.requestDetail.cancelModal.reasonLabel}
            </label>
            <textarea
              rows={2}
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder={t.requestDetail.cancelModal.reasonPlaceholder}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-rose-500 focus:outline-none"
            />
          </div>
        </div>
      </Dialog>

      {/* Reschedule Dialog */}
      <Dialog
        isOpen={showRescheduleModal}
        onClose={() => setShowRescheduleModal(false)}
        title={t.requestDetail.rescheduleModal.title}
        variant="primary"
        confirmLabel={rescheduleMutation.isPending ? t.requestDetail.rescheduleModal.submittingBtn : t.requestDetail.rescheduleModal.confirmBtn}
        cancelLabel={t.requestDetail.rescheduleModal.keepBtn}
        isLoading={rescheduleMutation.isPending}
        onConfirm={() => {
          if (!rescheduleTime.trim()) return;
          rescheduleMutation.mutate({
            preferred_time: rescheduleTime.trim(),
            reason: rescheduleReason.trim() || undefined,
          });
        }}
      >
        <div className="space-y-3 text-xs text-slate-600">
          <div className="p-3 bg-sky-50 rounded-xl border border-sky-200 text-sky-900 leading-relaxed">
            {t.requestDetail.rescheduleModal.importantNotice}
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              {t.requestDetail.rescheduleModal.newTimeLabel}
            </label>
            <input
              type="text"
              required
              value={rescheduleTime}
              onChange={(e) => setRescheduleTime(e.target.value)}
              placeholder={t.requestDetail.rescheduleModal.newTimePlaceholder}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              {t.requestDetail.rescheduleModal.reasonLabel}
            </label>
            <textarea
              rows={2}
              value={rescheduleReason}
              onChange={(e) => setRescheduleReason(e.target.value)}
              placeholder={t.requestDetail.rescheduleModal.reasonPlaceholder}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
          </div>
        </div>
      </Dialog>
    </div>
  );
};
