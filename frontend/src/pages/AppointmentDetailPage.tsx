import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchAppointmentDetail,
  completeAppointment,
  cancelAppointment,
  startAppointment,
  reassignAppointment,
} from '../api/appointments';
import { useAuth } from '../auth/useAuth';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorMessage } from '../components/common/ErrorMessage';
import { AuditTimeline } from '../components/common/AuditTimeline';
import { formatTimeRangeZh, formatDateTimeZh } from '../utils/dateTime';
import {
  ArrowLeft,
  Calendar,
  Clock,
  User,
  Phone,
  Mail,
  MapPin,
  CheckCircle,
  XCircle,
  ExternalLink,
  Loader2,
  PlayCircle,
  UserCheck,
  FileText,
  Wrench,
} from 'lucide-react';
import { operator } from '../locales/zh-CN/operator';
import { getServiceTypeText } from '../locales';

export const AppointmentDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { canAct, isViewer } = useAuth();
  const queryClient = useQueryClient();
  const t = operator.appointments.detail;

  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [showCompleteModal, setShowCompleteModal] = useState(false);
  const [completionNotes, setCompletionNotes] = useState('');
  const [resolutionSummary, setResolutionSummary] = useState('');
  const [showReassignModal, setShowReassignModal] = useState(false);
  const [reassignTechId, setReassignTechId] = useState('');
  const [reassignReason, setReassignReason] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    data: appt,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['appointment', id],
    queryFn: () => fetchAppointmentDetail(id!),
    enabled: !!id,
  });

  const startMutation = useMutation({
    mutationFn: () => startAppointment(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointment', id] });
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
    onError: (err: any) => {
      setActionError(err.message || '签到开工操作失败，请重试');
    },
  });

  const completeMutation = useMutation({
    mutationFn: () =>
      completeAppointment(id!, {
        completion_notes: completionNotes || undefined,
        resolution_summary: resolutionSummary || undefined,
      }),
    onSuccess: () => {
      setShowCompleteModal(false);
      queryClient.invalidateQueries({ queryKey: ['appointment', id] });
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
    onError: (err: any) => {
      setActionError(err.message || '确认完工失败，请重试');
    },
  });

  const reassignMutation = useMutation({
    mutationFn: () =>
      reassignAppointment(id!, {
        technician_id: reassignTechId ? parseInt(reassignTechId, 10) : undefined,
        reason: reassignReason || undefined,
      }),
    onSuccess: () => {
      setShowReassignModal(false);
      queryClient.invalidateQueries({ queryKey: ['appointment', id] });
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
    onError: (err: any) => {
      setActionError(err.message || '改派工程师失败，请重试');
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (reason?: string) => cancelAppointment(id!, reason),
    onSuccess: () => {
      setShowCancelModal(false);
      queryClient.invalidateQueries({ queryKey: ['appointment', id] });
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
    onError: (err: any) => {
      setActionError(err.message || '取消预约失败，请重试');
    },
  });

  if (isLoading) {
    return <LoadingSpinner label="正在加载预约详情…" className="py-24" />;
  }

  if (isError || !appt) {
    return (
      <ErrorMessage
        title="无法加载预约详情"
        message={(error as any)?.message || '未找到该上门预约记录'}
        onRetry={() => refetch()}
      />
    );
  }

  const isCompleted = appt.status === 'completed';
  const isCancelled = appt.status === 'cancelled';

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div>
        <Link
          to="/appointments"
          className="inline-flex items-center text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors mb-3 group"
        >
          <ArrowLeft className="w-3.5 h-3.5 mr-1 group-hover:-translate-x-0.5 transition-transform" />
          {t.backToList}
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                {t.title.replace('{id}', String(appt.id))}
              </h1>
              <StatusBadge type="status" value={appt.status} />
            </div>
            <p className="text-xs text-slate-500 mt-1">
              创建时间：{formatDateTimeZh(appt.created_at)}
            </p>
          </div>

          {/* Operator Action Buttons */}
          {canAct && (
            <div className="flex flex-wrap items-center gap-2">
              {/* Start Service */}
              {(appt.capabilities?.can_start ?? (appt.status === 'scheduled')) && (
                <button
                  type="button"
                  onClick={() => startMutation.mutate()}
                  disabled={startMutation.isPending}
                  className="inline-flex items-center px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 shadow-sm cursor-pointer"
                >
                  {startMutation.isPending ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                  ) : (
                    <PlayCircle className="w-3.5 h-3.5 mr-1" />
                  )}
                  {t.lifecycleActions.startService}
                </button>
              )}

              {/* Complete Service */}
              {(appt.capabilities?.can_complete ?? (appt.status === 'in_progress' || appt.status === 'scheduled')) && (
                <button
                  type="button"
                  onClick={() => setShowCompleteModal(true)}
                  disabled={completeMutation.isPending}
                  className="inline-flex items-center px-3.5 py-1.5 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 shadow-sm cursor-pointer"
                >
                  {completeMutation.isPending ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                  ) : (
                    <CheckCircle className="w-3.5 h-3.5 mr-1" />
                  )}
                  {t.lifecycleActions.completeService}
                </button>
              )}

              {/* Reassign Technician */}
              {(appt.capabilities?.can_reassign ?? (appt.status === 'scheduled')) && (
                <button
                  type="button"
                  onClick={() => setShowReassignModal(true)}
                  disabled={reassignMutation.isPending}
                  className="inline-flex items-center px-3 py-1.5 border border-slate-300 rounded-lg text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 shadow-sm cursor-pointer"
                >
                  <UserCheck className="w-3.5 h-3.5 mr-1 text-indigo-600" />
                  {t.lifecycleActions.reschedule}
                </button>
              )}

              {/* Cancel Appointment */}
              {(appt.capabilities?.can_cancel ?? (!isCompleted && !isCancelled)) && (
                <button
                  type="button"
                  onClick={() => setShowCancelModal(true)}
                  disabled={cancelMutation.isPending}
                  className="inline-flex items-center px-3 py-1.5 border border-slate-300 rounded-lg text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 shadow-sm cursor-pointer"
                >
                  <XCircle className="w-3.5 h-3.5 mr-1 text-rose-500" />
                  {t.lifecycleActions.cancel}
                </button>
              )}
            </div>
          )}

          {isViewer && (
            <span className="text-xs text-slate-500 bg-slate-100 px-2.5 py-1 rounded-md border border-slate-200 font-medium">
              只读角色：仅供查看
            </span>
          )}
        </div>
      </div>

      {actionError && (
        <ErrorMessage message={actionError} onRetry={() => setActionError(null)} />
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Appointment Schedule & Technician Info */}
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 mb-4">
              <Calendar className="w-4 h-4 text-indigo-600" />
              {t.scheduleTitle}
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-slate-50 p-4 rounded-lg border border-slate-100 text-xs">
              <div>
                <span className="text-slate-400 block mb-1">上门时间窗口 (中国标准时间)</span>
                <span className="font-semibold text-slate-900 font-mono text-sm">
                  {formatTimeRangeZh(appt.start_time, appt.end_time)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-1">{t.technicianTitle}</span>
                <span className="font-semibold text-slate-900 text-sm">
                  {appt.technician?.name || '待指派'}
                </span>
                <span className="text-slate-400 block text-[11px]">
                  服务网点 / 区域：{appt.technician?.service_area || '天河区'}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-1">服务类型</span>
                <span className="font-medium text-slate-800">
                  {getServiceTypeText(appt.service_request?.service_type)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-1">现场服务地址</span>
                <span className="font-medium text-slate-800 flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-slate-400" />
                  {appt.service_request?.location || '客户指定现场'}
                </span>
              </div>
              {appt.started_at && (
                <div>
                  <span className="text-slate-400 block mb-1">{t.actualStart}</span>
                  <span className="font-medium text-slate-800">
                    {formatDateTimeZh(appt.started_at)}
                  </span>
                </div>
              )}
              {appt.completed_at && (
                <div>
                  <span className="text-slate-400 block mb-1">{t.actualComplete}</span>
                  <span className="font-medium text-slate-800">
                    {formatDateTimeZh(appt.completed_at)}
                  </span>
                </div>
              )}
              {appt.rescheduled_from_appointment_id && (
                <div>
                  <span className="text-slate-400 block mb-1">改期自历史预约</span>
                  <Link
                    to={`/appointments/${appt.rescheduled_from_appointment_id}`}
                    className="font-semibold text-indigo-600 hover:underline"
                  >
                    预约单 #{appt.rescheduled_from_appointment_id}
                  </Link>
                </div>
              )}
              {appt.replaced_by_appointment_id && (
                <div>
                  <span className="text-slate-400 block mb-1">已被新预约单替代</span>
                  <Link
                    to={`/appointments/${appt.replaced_by_appointment_id}`}
                    className="font-semibold text-indigo-600 hover:underline"
                  >
                    预约单 #{appt.replaced_by_appointment_id}
                  </Link>
                </div>
              )}
            </div>

            {(appt.completion_notes || appt.resolution_summary) && (
              <div className="mt-4 p-3 bg-emerald-50 rounded-lg border border-emerald-200 text-xs space-y-1">
                <div className="font-semibold text-emerald-900">{t.completionNotes}</div>
                {appt.resolution_summary && (
                  <p className="text-emerald-800">
                    <strong>验收结果：</strong>{appt.resolution_summary}
                  </p>
                )}
                {appt.completion_notes && (
                  <p className="text-emerald-700">
                    <strong>工程师备注：</strong>{appt.completion_notes}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Linked Service Request Card */}
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <FileText className="w-4 h-4 text-indigo-600" />
                {t.serviceInfoTitle}
              </h3>
              {appt.service_request && (
                <Link
                  to={`/service-requests/${appt.service_request.id}`}
                  className="text-xs font-semibold text-indigo-600 hover:underline flex items-center gap-1"
                >
                  查看完整工单 #{appt.service_request.id}
                  <ExternalLink className="w-3 h-3" />
                </Link>
              )}
            </div>

            {appt.service_request ? (
              <div className="space-y-3 text-xs">
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 text-slate-700">
                  {appt.service_request.raw_message || '客户未填写附加描述。'}
                </div>
                <div className="flex items-center justify-between text-slate-600 pt-1">
                  <span>紧急程度：<StatusBadge type="urgency" value={appt.service_request.urgency} /></span>
                  <span>预约状态：<StatusBadge type="status" value={appt.status} /></span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-400">无关联工单信息</p>
            )}
          </div>
        </div>

        {/* Right Col: Customer & Audit */}
        <div className="space-y-6">
          {/* Customer Card */}
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 mb-4">
              <User className="w-4 h-4 text-indigo-600" />
              报修客户联系方式
            </h3>
            <div className="space-y-3 text-xs">
              <div>
                <span className="text-slate-400 block mb-0.5">客户姓名</span>
                <span className="font-semibold text-slate-900 text-sm">
                  {appt.customer?.name || '客户'}
                </span>
              </div>
              <div className="pt-2 border-t border-slate-100 flex items-center gap-2 text-slate-700">
                <Mail className="w-3.5 h-3.5 text-slate-400" />
                <span>{appt.customer?.email || '—'}</span>
              </div>
              <div className="pt-2 border-t border-slate-100 flex items-center gap-2 text-slate-700">
                <Phone className="w-3.5 h-3.5 text-slate-400" />
                <span>{appt.customer?.phone || '—'}</span>
              </div>
            </div>
          </div>

          {/* Audit Trail */}
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 mb-4">
              <Clock className="w-4 h-4 text-indigo-600" />
              流转节点与审计记录
            </h3>
            <AuditTimeline events={appt.timeline} />
          </div>
        </div>
      </div>

      {/* Cancel Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl space-y-4">
            <h3 className="text-base font-bold text-slate-900">取消上门预约 #{appt.id}</h3>
            <p className="text-xs text-slate-500">
              您确定要取消本次上门预约吗？此操作将更新预约状态并记录系统审计日志。
            </p>

            <textarea
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="请输入取消原因（如：客户改期、设备已自行恢复等）…"
              rows={3}
              className="w-full text-xs rounded-lg border-slate-300 border p-2.5 focus:border-rose-500 focus:ring-rose-500"
            />

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowCancelModal(false)}
                disabled={cancelMutation.isPending}
                className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-slate-800 cursor-pointer"
              >
                保留预约
              </button>
              <button
                type="button"
                onClick={() => cancelMutation.mutate(cancelReason)}
                disabled={cancelMutation.isPending}
                className="inline-flex items-center px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 disabled:opacity-50 cursor-pointer"
              >
                {cancelMutation.isPending ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                ) : (
                  <XCircle className="w-3.5 h-3.5 mr-1" />
                )}
                确认取消预约
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Complete Modal */}
      {showCompleteModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl space-y-4">
            <h3 className="text-base font-bold text-slate-900">确认完工 #{appt.id}</h3>
            <p className="text-xs text-slate-500">
              录入竣工验收说明与现场排查记录。确认完工将闭环当前服务单，并触发客户回访。
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  竣工验收结果 (面向客户展示)
                </label>
                <input
                  type="text"
                  value={resolutionSummary}
                  onChange={(e) => setResolutionSummary(e.target.value)}
                  placeholder="例如：已更换压缩机启辉电容并清洗滤网，设备运行正常。"
                  className="w-full text-xs rounded-lg border-slate-300 border p-2.5 focus:border-emerald-500 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  现场维保记录与诊断备注 (选填)
                </label>
                <textarea
                  value={completionNotes}
                  onChange={(e) => setCompletionNotes(e.target.value)}
                  placeholder="请输入补充维保技术参数或配件使用说明…"
                  rows={3}
                  className="w-full text-xs rounded-lg border-slate-300 border p-2.5 focus:border-emerald-500 focus:ring-emerald-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowCompleteModal(false)}
                disabled={completeMutation.isPending}
                className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-slate-800 cursor-pointer"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => completeMutation.mutate()}
                disabled={completeMutation.isPending}
                className="inline-flex items-center px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 cursor-pointer"
              >
                {completeMutation.isPending ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                ) : (
                  <CheckCircle className="w-3.5 h-3.5 mr-1" />
                )}
                确认完工验收
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reassign Modal */}
      {showReassignModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl space-y-4">
            <h3 className="text-base font-bold text-slate-900">改派服务工程师 #{appt.id}</h3>
            <p className="text-xs text-slate-500">
              将当前上门任务改派给其他工程师。若留空工号，系统将基于就近网格自动指派。
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  目标工程师工号 (选填)
                </label>
                <input
                  type="number"
                  value={reassignTechId}
                  onChange={(e) => setReassignTechId(e.target.value)}
                  placeholder="例如：2 (留空则由系统智能分配)"
                  className="w-full text-xs rounded-lg border-slate-300 border p-2.5 focus:border-indigo-500 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  改派原因说明
                </label>
                <input
                  type="text"
                  value={reassignReason}
                  onChange={(e) => setReassignReason(e.target.value)}
                  placeholder="例如：原工程师设备故障、突发请假或客户指定更换"
                  className="w-full text-xs rounded-lg border-slate-300 border p-2.5 focus:border-indigo-500 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowReassignModal(false)}
                disabled={reassignMutation.isPending}
                className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-slate-800 cursor-pointer"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => reassignMutation.mutate()}
                disabled={reassignMutation.isPending}
                className="inline-flex items-center px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 cursor-pointer"
              >
                {reassignMutation.isPending ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                ) : (
                  <UserCheck className="w-3.5 h-3.5 mr-1" />
                )}
                确认改派任务
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
