import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { fetchDashboardSummary } from '../api/dashboard';
import { fetchServiceRequests } from '../api/serviceRequests';
import { ServiceRequestListItem } from '../types/api';
import { formatDateTimeZh } from '../utils/dateTime';
import {
  CardSkeleton,
  TableSkeleton,
  StatusBadge,
  ErrorState,
  Drawer,
  Button,
  DataTable,
  Column,
} from '../components/ui';
import {
  Clock,
  CalendarCheck2,
  AlertOctagon,
  AlertTriangle,
  Layers,
  ArrowUpRight,
  RefreshCw,
  Sparkles,
  CheckCircle2,
  ExternalLink,
  ShieldAlert,
  Inbox,
  User,
  MapPin,
  FileText,
} from 'lucide-react';
import { operator } from '../locales/zh-CN/operator';
import { getServiceTypeText } from '../locales';

export const OverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedRequest, setSelectedRequest] = useState<ServiceRequestListItem | null>(null);
  const t = operator.overview;

  const {
    data: summary,
    isLoading: isSummaryLoading,
    isError: isSummaryError,
    error: summaryError,
    refetch: refetchSummary,
    isFetching: isSummaryFetching,
  } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: fetchDashboardSummary,
    refetchInterval: 15000,
  });

  const {
    data: activeRequests,
    isLoading: isRequestsLoading,
    refetch: refetchRequests,
  } = useQuery({
    queryKey: ['action-queue-requests'],
    queryFn: () => fetchServiceRequests({ limit: 20 }),
    refetchInterval: 15000,
  });

  const handleRefreshAll = () => {
    refetchSummary();
    refetchRequests();
  };

  if (isSummaryLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-64 bg-slate-200/70 rounded-md animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-5">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
        <TableSkeleton rows={6} />
      </div>
    );
  }

  if (isSummaryError) {
    return (
      <ErrorState
        title="加载调度监控数据失败"
        message={(summaryError as any)?.message || '获取调度概览数据时发生异常，请重试。'}
        onRetry={handleRefreshAll}
      />
    );
  }

  // Calculate deterministic SLA Health percentage
  const totalRequests = summary?.open_service_requests || 0;
  const breachedCount = summary?.sla_breached_count || 0;
  const atRiskCount = summary?.sla_at_risk_count || 0;
  const waitingApprovalCount = summary?.waiting_approval_count || 0;
  const openEscalationsCount = summary?.open_escalations_count || 0;
  const todayAppointments = summary?.today_appointments_count || 0;
  const pendingOutbox = summary?.pending_outbox_count || 0;

  const slaComplianceRate =
    totalRequests > 0
      ? Math.max(0, Math.round(((totalRequests - breachedCount) / totalRequests) * 100))
      : 100;

  // Filter and sort Action Queue items:
  // Priority: (1) waiting_for_approval, (2) urgency emergency, (3) sla at risk / breached, (4) newer
  const requestList: ServiceRequestListItem[] = Array.isArray(activeRequests)
    ? activeRequests
    : (activeRequests as any)?.items || [];
  const actionQueueItems = requestList
    .slice()
    .sort((a, b) => {
      const getPriorityScore = (item: ServiceRequestListItem) => {
        let score = 0;
        if (item.status === 'waiting_for_approval') score += 100;
        if (item.urgency === 'emergency') score += 80;
        if (item.sla_status === 'breached') score += 60;
        if (item.sla_status === 'at_risk') score += 40;
        if (item.urgency === 'high') score += 20;
        return score;
      };
      const scoreDiff = getPriorityScore(b) - getPriorityScore(a);
      if (scoreDiff !== 0) return scoreDiff;
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    })
    .slice(0, 8);

  const columns: Column<ServiceRequestListItem>[] = [
    {
      header: t.tableHeaders.id,
      accessor: (row) => (
        <span className="font-mono font-bold text-slate-900">#{row.id}</span>
      ),
      className: 'w-24',
    },
    {
      header: t.tableHeaders.urgency,
      accessor: (row) => <StatusBadge type="urgency" value={row.urgency} />,
    },
    {
      header: t.tableHeaders.customerService,
      accessor: (row) => (
        <div>
          <div className="font-semibold text-slate-900">{row.customer_name}</div>
          <div className="text-[11px] text-slate-500">
            {getServiceTypeText(row.service_type)} • {row.location || '待确认位置'}
          </div>
        </div>
      ),
    },
    {
      header: t.tableHeaders.status,
      accessor: (row) => <StatusBadge type="status" value={row.status} />,
    },
    {
      header: t.tableHeaders.sla,
      accessor: (row) => <StatusBadge type="sla" value={row.sla_status} />,
    },
    {
      header: t.tableHeaders.receivedAt,
      accessor: (row) => (
        <span className="text-slate-500 font-mono text-[11px]">
          {formatDateTimeZh(row.created_at)}
        </span>
      ),
    },
    {
      header: t.tableHeaders.action,
      accessor: (row) => (
        <div className="flex items-center justify-end gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => setSelectedRequest(row)}
            className="px-2.5 py-1 text-xs font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-md transition-colors cursor-pointer"
          >
            {t.actionQueue.quickPreview}
          </button>
          <Link
            to={`/service-requests/${row.id}`}
            className="p-1 text-slate-400 hover:text-slate-700 transition-colors"
            title="查看完整工单"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        </div>
      ),
      className: 'text-right',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{t.pageTitle}</h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            {t.pageSubtitle}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefreshAll}
          isLoading={isSummaryFetching}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          className="self-start sm:self-auto"
        >
          {t.refreshBtn}
        </Button>
      </div>

      {/* Bento Grid (Hero Section) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-5">
        {/* Bento Item 1: Needs Attention (High Priority Hero Card - col-span-5) */}
        <div className="lg:col-span-5 bg-gradient-to-br from-purple-900 via-indigo-900 to-slate-900 rounded-2xl p-6 text-white shadow-elevated flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none">
            <ShieldAlert className="w-40 h-40" />
          </div>

          <div>
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-white/10 text-purple-200 border border-white/15">
                <Clock className="w-3 h-3 text-purple-300" />
                {t.bento.attentionTitle}
              </span>
              <span className="text-xs text-purple-300 font-mono">实时流转看板</span>
            </div>

            <h3 className="text-lg font-bold text-white mt-3">{t.actionQueue.title}</h3>
            <p className="text-xs text-purple-200/80 mt-0.5 leading-relaxed">
              {t.bento.attentionSubtitle}
            </p>

            <div className="mt-5 grid grid-cols-3 gap-3">
              <Link
                to="/service-requests?status=waiting_for_approval"
                className="bg-white/10 hover:bg-white/15 border border-white/15 rounded-xl p-3 text-center transition-colors group"
              >
                <div className="text-2xl font-black text-white group-hover:scale-105 transition-transform font-mono">
                  {waitingApprovalCount}
                </div>
                <div className="text-[11px] text-purple-200 font-medium mt-1 truncate">
                  {t.bento.waitingApproval}
                </div>
              </Link>

              <Link
                to="/escalations"
                className="bg-white/10 hover:bg-white/15 border border-white/15 rounded-xl p-3 text-center transition-colors group"
              >
                <div className="text-2xl font-black text-rose-300 group-hover:scale-105 transition-transform font-mono">
                  {openEscalationsCount}
                </div>
                <div className="text-[11px] text-rose-200 font-medium mt-1 truncate">
                  {t.bento.openEscalations}
                </div>
              </Link>

              <div className="bg-white/10 border border-white/15 rounded-xl p-3 text-center">
                <div className="text-2xl font-black text-amber-300 font-mono">
                  {atRiskCount}
                </div>
                <div className="text-[11px] text-amber-200 font-medium mt-1 truncate">
                  {t.bento.slaAtRisk}
                </div>
              </div>
            </div>
          </div>

          <div className="mt-5 pt-4 border-t border-white/15 flex items-center justify-between text-xs text-purple-200">
            <span>调度重点：待确认方案与升级工单</span>
            <Link
              to="/service-requests?status=waiting_for_approval"
              className="inline-flex items-center text-white font-semibold hover:underline"
            >
              立即处理 →
            </Link>
          </div>
        </div>

        {/* Bento Item 2: SLA Compliance Health (col-span-3) */}
        <div className="lg:col-span-3 bg-white rounded-2xl border border-slate-200 p-6 shadow-card flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                {t.bento.slaHealthRate}
              </span>
              <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                <CheckCircle2 className="w-4 h-4" />
              </div>
            </div>

            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-slate-900 font-mono">
                {slaComplianceRate}%
              </span>
              <span className="text-xs font-medium text-emerald-600">履约受控</span>
            </div>

            <p className="text-xs text-slate-400 mt-1">全周期服务响应与上门承诺率</p>

            {/* Visual Health Bar */}
            <div className="mt-4 space-y-2">
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden flex">
                <div
                  style={{ width: `${slaComplianceRate}%` }}
                  className="bg-emerald-500 h-full"
                />
                <div
                  style={{ width: `${Math.min(100 - slaComplianceRate, 20)}%` }}
                  className="bg-amber-500 h-full"
                />
              </div>

              <div className="flex items-center justify-between text-xs pt-1">
                <span className="text-slate-600 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  时效预警：<strong>{atRiskCount}</strong>
                </span>
                <span className="text-slate-600 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-rose-500" />
                  已超时：<strong>{breachedCount}</strong>
                </span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-500">
            {breachedCount > 0 ? (
              <span className="text-rose-600 font-medium">⚠️ 存在超期未履约工单，需优先派工</span>
            ) : (
              <span className="text-emerald-700 font-medium">✓ 当前全域工单时效受控</span>
            )}
          </div>
        </div>

        {/* Bento Item 3: Today's Appointments & Ops (col-span-4) */}
        <div className="lg:col-span-4 bg-white rounded-2xl border border-slate-200 p-6 shadow-card flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                {t.bento.todayTitle}
              </span>
              <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                <CalendarCheck2 className="w-4 h-4" />
              </div>
            </div>

            <div className="mt-3 flex items-baseline justify-between">
              <div className="text-3xl font-bold text-slate-900 font-mono">
                {todayAppointments}
              </div>
              <Link
                to="/appointments"
                className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-0.5"
              >
                查看日程 →
              </Link>
            </div>
            <p className="text-xs text-slate-400 mt-1">今日已锁定的服务工程师上门任务数</p>

            <div className="mt-5 grid grid-cols-2 gap-3 pt-3 border-t border-slate-100 text-xs">
              <div>
                <span className="text-slate-400 block text-[11px]">{t.bento.openRequests}</span>
                <span className="text-base font-bold text-slate-800 font-mono mt-0.5 block">
                  {summary?.open_service_requests ?? 0}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Outbox 待投递消息</span>
                <span className="text-base font-bold text-slate-800 font-mono mt-0.5 block">
                  {pendingOutbox}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500 flex items-center justify-between">
            <span>历史服务任务累计</span>
            <span className="font-mono font-semibold text-slate-700">
              {summary?.total_appointments_count ?? 0} 单
            </span>
          </div>
        </div>
      </div>

      {/* Bento Item 4: AI Operations Summary (Deterministic & Grounded) */}
      <div className="rounded-2xl border border-indigo-100 bg-gradient-to-r from-indigo-50/70 via-sky-50/50 to-white p-5 shadow-xs">
        <div className="flex items-start gap-3.5">
          <div className="w-9 h-9 rounded-xl bg-indigo-600 text-white flex items-center justify-center shrink-0 shadow-xs">
            <Sparkles className="w-4 h-4" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-indigo-950">
                调度引擎智能洞察摘要
              </h3>
              <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 border border-indigo-200">
                真实运行指标
              </span>
            </div>

            <div className="mt-2 text-xs text-slate-700 space-y-1 leading-relaxed">
              {waitingApprovalCount > 0 && (
                <p className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-purple-600 shrink-0" />
                  <span>
                    当前有 <strong>{waitingApprovalCount} 笔工单</strong> 已智能匹配最佳工程师及上门时隙，等待调度员人工确认派发。
                  </span>
                </p>
              )}
              {openEscalationsCount > 0 && (
                <p className="flex items-center gap-1.5 text-rose-800">
                  <AlertOctagon className="w-3.5 h-3.5 text-rose-600 shrink-0" />
                  <span>
                    发现 <strong>{openEscalationsCount} 笔升级工单</strong> 触发调度预警或履约异常，需调度员紧急协同介入。
                  </span>
                </p>
              )}
              {atRiskCount > 0 && (
                <p className="flex items-center gap-1.5 text-amber-800">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                  <span>
                    有 <strong>{atRiskCount} 笔工单</strong> 正在逼近 SLA 服务承诺时限，请加速指派工程师。
                  </span>
                </p>
              )}
              {pendingOutbox > 0 && (
                <p className="flex items-center gap-1.5 text-slate-600">
                  <Layers className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                  <span>
                    Outbox 事务发件箱队列中有 <strong>{pendingOutbox} 条消息</strong> 待同步至 Google Calendar 与异步通知管道。
                  </span>
                </p>
              )}
              {waitingApprovalCount === 0 && openEscalationsCount === 0 && atRiskCount === 0 && (
                <p className="flex items-center gap-1.5 text-emerald-800">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span>
                    全域工单运行负载均衡，无积压待确认派单、无未处理升级，SLA 达标率 100%。
                  </span>
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Action Queue Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900 tracking-tight">
              {t.actionQueue.title}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              根据紧急度、待审批状态与 SLA 履约截止时间综合加权排序。点击行可快速预览。
            </p>
          </div>
          <Link
            to="/service-requests"
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
          >
            查看全部工单 →
          </Link>
        </div>

        <DataTable
          columns={columns}
          data={actionQueueItems}
          isLoading={isRequestsLoading}
          onRowClick={(row) => setSelectedRequest(row)}
          emptyTitle={t.actionQueue.emptyTitle}
          emptyDescription={t.actionQueue.emptyDesc}
        />
      </div>

      {/* Quick Preview Side Drawer */}
      <Drawer
        isOpen={!!selectedRequest}
        onClose={() => setSelectedRequest(null)}
        title={selectedRequest ? `工单编号 #${selectedRequest.id}` : '工单详情快速预览'}
        subtitle={selectedRequest ? `接收于 ${formatDateTimeZh(selectedRequest.created_at)}` : ''}
        badge={
          selectedRequest && (
            <StatusBadge type="status" value={selectedRequest.status} />
          )
        }
        footer={
          selectedRequest && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedRequest(null)}
              >
                关闭
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  const id = selectedRequest.id;
                  setSelectedRequest(null);
                  navigate(`/service-requests/${id}`);
                }}
                rightIcon={<ArrowUpRight className="w-3.5 h-3.5" />}
              >
                {t.actionQueue.openDetail}
              </Button>
            </>
          )
        }
      >
        {selectedRequest && (
          <div className="space-y-6">
            {/* Status & Priority Row */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500 font-medium">SLA 服务时效</span>
                <StatusBadge type="sla" value={selectedRequest.sla_status} />
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500 font-medium">紧急程度</span>
                <StatusBadge type="urgency" value={selectedRequest.urgency} />
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500 font-medium">报修分类</span>
                <span className="font-semibold text-slate-800">
                  {getServiceTypeText(selectedRequest.service_type)}
                </span>
              </div>
            </div>

            {/* Customer Information */}
            <div>
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                客户基本信息
              </h4>
              <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-2 text-xs">
                <div className="flex items-center gap-2 text-slate-800 font-semibold">
                  <User className="w-3.5 h-3.5 text-slate-400" />
                  {selectedRequest.customer_name}
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                  <MapPin className="w-3.5 h-3.5 text-slate-400" />
                  {selectedRequest.location || '待确认位置'}
                </div>
                <div className="text-slate-500 text-[11px] pt-1 border-t border-slate-100">
                  客户编号：#{selectedRequest.customer_id} • 电子邮箱：{selectedRequest.customer_email || '未提供'}
                </div>
              </div>
            </div>

            {/* Issue Description */}
            <div>
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                客户原始报修诉求
              </h4>
              <div className="bg-slate-50 rounded-xl border border-slate-200 p-4 text-xs text-slate-700 leading-relaxed font-sans">
                {selectedRequest.raw_message || '客户未填写附加描述。'}
              </div>
            </div>

            {/* Action Callout if Awaiting Approval */}
            {selectedRequest.status === 'waiting_for_approval' && (
              <div className="p-4 rounded-xl bg-purple-50 border border-purple-200 text-purple-900 text-xs flex items-start gap-3">
                <Clock className="w-4 h-4 text-purple-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold">待人工确认派单</div>
                  <div className="text-purple-700 mt-0.5">
                    系统已智能预选工程师候选人与建议上门时间，请进入工单详情核准或调整派单。
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
};
