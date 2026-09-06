import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchServiceRequestDetail,
  submitApproval,
} from '../api/serviceRequests';
import {
  StatusBadge,
  DetailSkeleton,
  ErrorState,
  Button,
} from '../components/ui';
import { AuditTimeline } from '../components/common/AuditTimeline';
import { DispatchRankingCard } from '../components/features/DispatchRankingCard';
import { AppointmentProposalCard } from '../components/features/AppointmentProposalCard';
import { formatDateTimeZh, formatSLARemaining } from '../utils/dateTime';
import { useAuth } from '../auth/useAuth';
import {
  ArrowLeft,
  User,
  Phone,
  Mail,
  MapPin,
  Wrench,
  Clock,
  CalendarCheck,
  CheckCircle2,
  FileText,
  ShieldCheck,
  Sparkles,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { operator } from '../locales/zh-CN/operator';
import { getServiceTypeText } from '../locales';

export const ServiceRequestDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { canAct, isViewer } = useAuth();
  const [actionError, setActionError] = useState<string | null>(null);
  const [showAllCandidates, setShowAllCandidates] = useState(false);
  const t = operator.requestDetail;

  const {
    data: sr,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['service-request', id],
    queryFn: () => fetchServiceRequestDetail(id!),
    enabled: !!id,
  });

  const approvalMutation = useMutation({
    mutationFn: ({ decision, reason }: { decision: 'approve' | 'reject'; reason?: string }) =>
      submitApproval(id!, { decision, reason }),
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ['service-request', id] });
      queryClient.invalidateQueries({ queryKey: ['service-requests'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
    onError: (err: any) => {
      if (err.status === 409) {
        setActionError(
          err.message || '建议的上门时隙已被占用或发生冲突，需要重新调度。'
        );
      } else {
        setActionError(err.message || '核准派单操作失败，请重试。');
      }
      queryClient.invalidateQueries({ queryKey: ['service-request', id] });
    },
  });

  if (isLoading) {
    return <DetailSkeleton />;
  }

  if (isError || !sr) {
    return (
      <ErrorState
        title="无法加载工单详情"
        message={(error as any)?.message || '未找到该服务工单或已被删除'}
        requestId={id}
        onRetry={() => refetch()}
      />
    );
  }

  const handleApprove = async (_note?: string) => {
    setActionError(null);
    await approvalMutation.mutateAsync({ decision: 'approve' });
  };

  const handleReject = async (reason?: string) => {
    setActionError(null);
    await approvalMutation.mutateAsync({ decision: 'reject', reason });
  };

  const topCandidate = sr.dispatch_rankings && sr.dispatch_rankings.length > 0 ? sr.dispatch_rankings[0] : null;
  const alternativeCandidates = sr.dispatch_rankings && sr.dispatch_rankings.length > 1 ? sr.dispatch_rankings.slice(1) : [];

  // Deterministic Grounded AI Context synthesis
  const getGroundedNextAction = () => {
    if (sr.status === 'waiting_for_approval' || sr.status === 'ready_for_review') {
      return '核对系统推荐的工程师与上门时段，人工确认并锁定排期。';
    }
    if (sr.status === 'scheduled') {
      return '上门预约已锁定，监控履约日工程师签到与作业动态。';
    }
    if (sr.status === 'needs_rescheduling' || sr.status === 'conflict') {
      return '检测到日程冲突或改派申请，正在重新评估候选工程师可用时隙。';
    }
    if (sr.status === 'completed') {
      return '维修作业已完成验收，工单归档并推送客户满意度评价。';
    }
    if (sr.status === 'cancelled') {
      return '服务需求已被客户或调度员取消，流转中止。';
    }
    return '工单正在调度引擎处理流转中。';
  };

  const serviceTypeText = getServiceTypeText(sr.service_type);
  const slaRemainingText = formatSLARemaining(sr.sla?.response_deadline);

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-24">
      {/* Back Navigation & Header */}
      <div>
        <Link
          to="/service-requests"
          className="inline-flex items-center text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors mb-3 group"
        >
          <ArrowLeft className="w-3.5 h-3.5 mr-1 group-hover:-translate-x-0.5 transition-transform" />
          {t.backToList}
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                {serviceTypeText} 工单 #{sr.id}
              </h1>
              <StatusBadge type="urgency" value={sr.urgency} />
              <StatusBadge type="status" value={sr.status} />
              {slaRemainingText && (
                <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${slaRemainingText.isBreached ? 'bg-rose-50 text-rose-800 border-rose-200' : 'bg-indigo-50 text-indigo-800 border-indigo-200'}`}>
                  服务时效：{slaRemainingText.isBreached ? '已超时 ' : '剩余 '}{slaRemainingText.text}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-1">
              接收时间：{formatDateTimeZh(sr.created_at)} • 客户编号：#{sr.customer_id}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <StatusBadge type="sla" value={sr.sla?.sla_status || 'on_track'} />
          </div>
        </div>
      </div>

      {/* Appointment Proposal Gate (Human-in-the-loop) */}
      {sr.proposal && (sr.status === 'waiting_for_approval' || sr.status === 'ready_for_review') && (
        <AppointmentProposalCard
          proposal={sr.proposal}
          isSubmitting={approvalMutation.isPending}
          errorMessage={actionError}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      )}

      {/* Confirmed Appointment Banner */}
      {sr.appointment && (
        <div className="rounded-2xl border border-emerald-200 bg-gradient-to-r from-emerald-50/80 to-white p-5 text-emerald-900 shadow-card flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center shrink-0 text-emerald-700">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-emerald-950">{t.confirmedAppointmentBanner.title}</h3>
              <p className="text-xs text-emerald-800 mt-0.5 leading-relaxed">
                已指派服务工程师 <strong>{sr.appointment.technician_name}</strong>，计划于{' '}
                {formatDateTimeZh(sr.appointment.start_time)} 到场履约。
              </p>
            </div>
          </div>
          <Link
            to={`/appointments/${sr.appointment.id}`}
            className="inline-flex items-center text-xs font-semibold text-emerald-800 bg-white border border-emerald-300 px-3.5 py-2 rounded-xl hover:bg-emerald-50 shadow-xs transition-colors self-start sm:self-auto shrink-0"
          >
            查看预约单 #{sr.appointment.id} →
          </Link>
        </div>
      )}

      {/* Main Grid: Request Info & SLA Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Customer & Intake Details + Dispatch Matching */}
        <div className="lg:col-span-2 space-y-6">
          {/* Intake Message Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-card">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-3">
              <FileText className="w-4 h-4 text-indigo-600" />
              {t.customerSection.issueDescription}
            </h3>
            <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl text-xs sm:text-sm text-slate-800 leading-relaxed whitespace-pre-wrap font-sans">
              {sr.raw_message || '客户未填写附加描述。'}
            </div>

            <div className="mt-4 grid grid-cols-2 gap-4 text-xs pt-4 border-t border-slate-100">
              <div>
                <span className="text-slate-400 block mb-1">{t.customerSection.serviceType}</span>
                <span className="font-semibold text-slate-800 flex items-center gap-1.5">
                  <Wrench className="w-3.5 h-3.5 text-slate-400" />
                  {serviceTypeText}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-1">{t.customerSection.location}</span>
                <span className="font-semibold text-slate-800 flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-slate-400" />
                  {sr.location || '待确认位置'}
                </span>
              </div>
            </div>
          </div>

          {/* Dispatch Ranking Engine (Explainable AI) */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-card space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-indigo-600" />
                <h3 className="text-sm font-bold text-slate-900">
                  {t.dispatchSection.title}
                </h3>
              </div>
              <span className="text-xs text-slate-400 font-mono">
                已综合评估 {sr.dispatch_rankings?.length || 0} 位候选工程师
              </span>
            </div>
            <p className="text-xs text-slate-500 leading-relaxed">
              {t.dispatchSection.subtitle}
            </p>

            <div className="pt-2 space-y-4">
              {topCandidate ? (
                <>
                  {/* Top Candidate Hero Card */}
                  <DispatchRankingCard
                    candidate={topCandidate}
                    isTopChoice={true}
                  />

                  {/* Alternative Candidates Section */}
                  {alternativeCandidates.length > 0 && (
                    <div className="pt-2">
                      <div className="flex items-center justify-between pb-2">
                        <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                          {t.dispatchSection.alternativeTitle} ({alternativeCandidates.length})
                        </h4>
                        <button
                          onClick={() => setShowAllCandidates((prev) => !prev)}
                          className="inline-flex items-center gap-1 text-xs text-indigo-600 font-semibold hover:underline cursor-pointer"
                        >
                          {showAllCandidates ? (
                            <>
                              <span>{t.dispatchSection.hideCandidates}</span>
                              <ChevronUp className="w-3.5 h-3.5" />
                            </>
                          ) : (
                            <>
                              <span>{t.dispatchSection.viewAllCandidates.replace('{count}', String(alternativeCandidates.length))}</span>
                              <ChevronDown className="w-3.5 h-3.5" />
                            </>
                          )}
                        </button>
                      </div>

                      {showAllCandidates && (
                        <div className="space-y-3 pt-2 animate-in fade-in duration-200">
                          {alternativeCandidates.map((candidate) => (
                            <DispatchRankingCard
                              key={candidate.technician_id}
                              candidate={candidate}
                              isTopChoice={false}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </>
              ) : (
                <div className="text-xs text-slate-500 py-6 text-center italic bg-slate-50 rounded-xl border border-dashed border-slate-200">
                  当前网格暂无满足技能资质的空闲工程师。
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Col: Grounded AI Operations Context + Customer Card + SLA */}
        <div className="space-y-6">
          {/* Grounded AI Context Panel */}
          <div className="rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-50/80 via-white to-sky-50/50 p-5 shadow-card space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                <Sparkles className="w-3.5 h-3.5" />
              </div>
              <h3 className="text-xs font-bold text-indigo-950 uppercase tracking-wider">
                调度引擎智能洞察
              </h3>
            </div>

            <div className="space-y-2.5 text-xs text-slate-700 pt-1">
              <div>
                <span className="text-[11px] text-slate-400 font-medium block">报修诉求综合特征</span>
                <span className="font-medium text-slate-800">
                  {serviceTypeText}，优先级评定为【{sr.urgency}】，服务地址位于 {sr.location || '待确认地点'}。
                </span>
              </div>

              <div>
                <span className="text-[11px] text-slate-400 font-medium block">首选推荐工程师</span>
                <span className="font-semibold text-indigo-700">
                  {topCandidate ? `${topCandidate.name} (匹配度 ${Math.round(topCandidate.score * 100)}%)` : '暂无匹配候选人'}
                </span>
              </div>

              <div>
                <span className="text-[11px] text-slate-400 font-medium block">服务时效承诺目标</span>
                <span className="font-medium text-slate-800">
                  响应时限目标：{sr.sla?.response_hours} 小时 • 完工时限目标：{sr.sla?.resolution_hours} 小时
                </span>
              </div>

              <div className="p-3 bg-white/80 rounded-xl border border-indigo-100/80">
                <span className="text-[10px] font-bold text-indigo-900 uppercase tracking-wider block mb-0.5">
                  推荐下一步调度动作
                </span>
                <span className="text-xs text-indigo-950 font-medium leading-relaxed">
                  {getGroundedNextAction()}
                </span>
              </div>
            </div>
          </div>

          {/* Customer Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-card">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-4">
              <User className="w-4 h-4 text-indigo-600" />
              {t.customerSection.title}
            </h3>
            <div className="space-y-3 text-xs">
              <div>
                <div className="text-slate-400 font-medium">{t.customerSection.customerName}</div>
                <div className="text-slate-900 font-semibold text-sm mt-0.5">
                  {sr.customer?.name || '未知客户'}
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center gap-2 text-slate-700">
                <Mail className="w-3.5 h-3.5 text-slate-400" />
                <span>{sr.customer?.email || '—'}</span>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center gap-2 text-slate-700">
                <Phone className="w-3.5 h-3.5 text-slate-400" />
                <span>{sr.customer?.phone || '—'}</span>
              </div>
            </div>
          </div>

          {/* SLA Tracking Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-card">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-4">
              <Clock className="w-4 h-4 text-indigo-600" />
              服务时效承诺 (SLA)
            </h3>
            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                <span className="text-slate-500">时效健康度</span>
                <StatusBadge type="sla" value={sr.sla?.sla_status || 'on_track'} />
              </div>

              <div className="pb-2 border-b border-slate-100">
                <span className="text-slate-400 block mb-1">响应时限目标</span>
                <div className="font-semibold text-slate-800">
                  {sr.sla?.response_hours} 小时内响应
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5 font-mono">
                  截止时间：{formatDateTimeZh(sr.sla?.response_deadline)}
                </div>
              </div>

              <div>
                <span className="text-slate-400 block mb-1">完工时限目标</span>
                <div className="font-semibold text-slate-800">
                  {sr.sla?.resolution_hours} 小时内完成
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5 font-mono">
                  截止时间：{formatDateTimeZh(sr.sla?.resolution_deadline)}
                </div>
              </div>
            </div>
          </div>

          {/* Audit Timeline */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-card">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-4">
              <CalendarCheck className="w-4 h-4 text-indigo-600" />
              {t.timeline.title}
            </h3>
            <AuditTimeline events={sr.timeline} />
          </div>
        </div>
      </div>

      {/* Sticky Bottom Action Bar */}
      <div className="fixed bottom-0 left-0 right-0 z-40 bg-white/90 backdrop-blur-md border-t border-slate-200 shadow-elevated py-3 px-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-xs font-bold text-slate-900 hidden sm:inline truncate">
              工单 #{sr.id}
            </span>
            <StatusBadge type="status" value={sr.status} />
            <StatusBadge type="sla" value={sr.sla?.sla_status || 'on_track'} />
          </div>

          <div className="flex items-center gap-3">
            {sr.proposal && (sr.status === 'waiting_for_approval' || sr.status === 'ready_for_review') && canAct && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleReject()}
                  disabled={approvalMutation.isPending}
                  className="border-rose-200 text-rose-700 hover:bg-rose-50"
                >
                  {t.dispatchSection.proposalCard.rejectBtn}
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => handleApprove()}
                  isLoading={approvalMutation.isPending}
                  className="bg-emerald-600 hover:bg-emerald-700"
                >
                  {t.dispatchSection.proposalCard.approveBtn}
                </Button>
              </>
            )}

            {sr.appointment && (
              <Link to={`/appointments/${sr.appointment.id}`}>
                <Button variant="primary" size="sm">
                  查看预约单 #{sr.appointment.id}
                </Button>
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
