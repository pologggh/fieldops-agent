import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchEscalationDetail,
  acknowledgeEscalation,
  resolveEscalation,
} from '../api/escalations';
import { useAuth } from '../auth/useAuth';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorMessage } from '../components/common/ErrorMessage';
import { formatDateTimeZh } from '../utils/dateTime';
import {
  ArrowLeft,
  AlertOctagon,
  CheckCircle,
  Clock,
  User,
  Phone,
  Mail,
  ExternalLink,
  Loader2,
  ShieldCheck,
} from 'lucide-react';

export const EscalationDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { canAct, isViewer } = useAuth();
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    data: esc,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['escalation', id],
    queryFn: () => fetchEscalationDetail(id!),
    enabled: !!id,
  });

  const ackMutation = useMutation({
    mutationFn: () => acknowledgeEscalation(id!),
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ['escalation', id] });
      queryClient.invalidateQueries({ queryKey: ['escalations'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
    onError: (err: any) => {
      setActionError(err.message || '确认已知晓操作失败，请重试');
    },
  });

  const resolveMutation = useMutation({
    mutationFn: () => resolveEscalation(id!),
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ['escalation', id] });
      queryClient.invalidateQueries({ queryKey: ['escalations'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
    onError: (err: any) => {
      setActionError(err.message || '标记解决失败，请重试');
    },
  });

  if (isLoading) {
    return <LoadingSpinner label="正在加载升级事件详情…" className="py-24" />;
  }

  if (isError || !esc) {
    return (
      <ErrorMessage
        title="无法加载升级事件详情"
        message={(error as any)?.message || '未找到该升级事件记录'}
        onRetry={() => refetch()}
      />
    );
  }

  const isResolved = esc.status === 'resolved';

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      {/* Back Button & Header */}
      <div>
        <Link
          to="/escalations"
          className="inline-flex items-center text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors mb-3 group"
        >
          <ArrowLeft className="w-3.5 h-3.5 mr-1 group-hover:-translate-x-0.5 transition-transform" />
          返回升级处理中心
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                升级事件 #{esc.id}
              </h1>
              <StatusBadge type="severity" value={esc.severity} />
              <StatusBadge type="status" value={esc.status} />
            </div>
            <p className="text-xs text-slate-500 mt-1">
              触发登记时间：{formatDateTimeZh(esc.created_at)}
            </p>
          </div>

          {/* Action Buttons */}
          {canAct && !isResolved && (
            <div className="flex items-center gap-2">
              {esc.status === 'open' && (
                <button
                  type="button"
                  onClick={() => ackMutation.mutate()}
                  disabled={ackMutation.isPending}
                  className="inline-flex items-center px-3 py-1.5 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 shadow-sm cursor-pointer"
                >
                  {ackMutation.isPending ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                  ) : (
                    <ShieldCheck className="w-3.5 h-3.5 mr-1 text-amber-600" />
                  )}
                  确认响应 (已知晓)
                </button>
              )}
              <button
                type="button"
                onClick={() => resolveMutation.mutate()}
                disabled={resolveMutation.isPending}
                className="inline-flex items-center px-3.5 py-1.5 border border-transparent rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 shadow-sm cursor-pointer"
              >
                {resolveMutation.isPending ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                ) : (
                  <CheckCircle className="w-3.5 h-3.5 mr-1" />
                )}
                确认问题解决并闭环
              </button>
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

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          {/* Escalation Context Card */}
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
            <div className="flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 text-rose-600" />
              <h3 className="text-sm font-semibold text-slate-900">升级原因与背景说明</h3>
            </div>

            <div className="p-4 bg-rose-50/50 border border-rose-100 rounded-lg text-sm text-rose-950 font-medium leading-relaxed">
              {esc.raw_message || '未登记附加描述。'}
            </div>

            <div className="text-xs text-slate-600 pt-2 flex items-center justify-between">
              <div>
                <span className="text-slate-400">关联服务工单：</span>
                <Link
                  to={`/service-requests/${esc.service_request_id}`}
                  className="font-semibold text-indigo-600 hover:underline inline-flex items-center gap-1"
                >
                  工单 #{esc.service_request_id}
                  <ExternalLink className="w-3 h-3" />
                </Link>
              </div>
              <StatusBadge type="urgency" value={esc.urgency} />
            </div>
          </div>
        </div>

        {/* Right Col: Customer Contact & SLA info */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 mb-4">
              <User className="w-4 h-4 text-indigo-600" />
              报修客户联系方式
            </h3>
            <div className="space-y-3 text-xs">
              <div>
                <div className="text-slate-400">客户姓名</div>
                <div className="text-slate-900 font-semibold text-sm mt-0.5">
                  {esc.customer_name}
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center gap-2 text-slate-700">
                <Mail className="w-3.5 h-3.5 text-slate-400" />
                <span>{esc.customer_email || '—'}</span>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center gap-2 text-slate-700">
                <Phone className="w-3.5 h-3.5 text-slate-400" />
                <span>{esc.customer_phone || '—'}</span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 mb-4">
              <Clock className="w-4 h-4 text-indigo-600" />
              SLA 服务时效状态
            </h3>
            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                <span className="text-slate-500">时效健康度</span>
                <StatusBadge type="sla" value={esc.sla?.sla_status || 'on_track'} />
              </div>

              <div>
                <span className="text-slate-400 block mb-1">完工履约截止时间</span>
                <div className="font-semibold text-slate-800 font-mono">
                  {formatDateTimeZh(esc.sla?.resolution_deadline)}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
