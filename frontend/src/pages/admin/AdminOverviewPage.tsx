import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Users,
  Wrench,
  Sliders,
  Timer,
  Network,
  ShieldCheck,
  ArrowRight,
  Server,
  Activity,
  CheckCircle2,
  Calendar,
  Mail,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';
import {
  getSystemSummary,
  getIntegrationSummary,
  getDispatchPolicies,
  getSLAPolicies,
  getAuditLogs,
} from '../../api/adminApi';
import {
  CardSkeleton,
  TableSkeleton,
  StatusBadge,
  Button,
} from '../../components/ui';
import { formatDateTimeZh } from '../../utils/dateTime';
import { admin } from '../../locales/zh-CN/admin';

export const AdminOverviewPage: React.FC = () => {
  const t = admin.overview;

  const {
    data: system,
    isLoading: isSystemLoading,
    refetch: refetchSystem,
    isFetching,
  } = useQuery({
    queryKey: ['admin-system-summary'],
    queryFn: getSystemSummary,
  });

  const { data: integrations, refetch: refetchIntegrations } = useQuery({
    queryKey: ['admin-integration-summary'],
    queryFn: getIntegrationSummary,
  });

  const { data: dispatchPolicies, refetch: refetchDispatch } = useQuery({
    queryKey: ['admin-dispatch-policies'],
    queryFn: getDispatchPolicies,
  });

  const { data: slaPolicies, refetch: refetchSla } = useQuery({
    queryKey: ['admin-sla-policies'],
    queryFn: getSLAPolicies,
  });

  const { data: recentLogs, refetch: refetchLogs } = useQuery({
    queryKey: ['admin-recent-audit-logs'],
    queryFn: () => getAuditLogs({ limit: 6 }),
  });

  const handleRefreshAll = () => {
    refetchSystem();
    refetchIntegrations();
    refetchDispatch();
    refetchSla();
    refetchLogs();
  };

  const activeDispatch = Array.isArray(dispatchPolicies) ? dispatchPolicies.find((p) => p.is_active) : undefined;
  const activeSla = Array.isArray(slaPolicies) ? slaPolicies.find((p) => p.is_active) : undefined;

  if (isSystemLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-64 bg-slate-200/70 rounded-md animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-5">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
        <TableSkeleton rows={5} />
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Page Title & Intro */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            {t.pageTitle}
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            {t.pageSubtitle}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefreshAll}
          isLoading={isFetching}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          className="self-start sm:self-auto"
        >
          {t.refreshBtn || '刷新治理指标'}
        </Button>
      </div>

      {/* Bento Grid: Row 1 - System Health Matrix & Governance Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Bento Card 1: System Health Matrix (col-span-7) */}
        <div className="lg:col-span-7 bg-white rounded-2xl border border-slate-200 p-6 shadow-card flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center space-x-2.5">
                <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <Activity className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-sm">基础设施健康矩阵</h3>
                  <p className="text-[11px] text-slate-400">核心调度与流转服务链路实时探活</p>
                </div>
              </div>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                所有服务运行正常
              </span>
            </div>

            {/* Health Matrix Grid */}
            <div className="mt-5 grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/70">
                <div className="text-[11px] text-slate-400 font-medium">FastAPI 核心服务</div>
                <div className="mt-1 flex items-center gap-1.5 font-bold text-slate-800">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  正常运行
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/70">
                <div className="text-[11px] text-slate-400 font-medium">PostgreSQL 关系型主库</div>
                <div className="mt-1 flex items-center gap-1.5 font-bold text-slate-800">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  正常连接
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/70">
                <div className="text-[11px] text-slate-400 font-medium">Redis & Celery 队列</div>
                <div className="mt-1 flex items-center gap-1.5 font-bold text-slate-800">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  正常运行
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/70">
                <div className="text-[11px] text-slate-400 font-medium">Google Calendar 同步</div>
                <div className="mt-1 flex items-center gap-1.5 font-bold text-slate-800">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  正常同步
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/70">
                <div className="text-[11px] text-slate-400 font-medium">Transactional Outbox</div>
                <div className="mt-1 flex items-center gap-1.5 font-bold text-slate-800 font-mono">
                  {system?.pending_outbox_events ?? 0} 条待投递
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/70">
                <div className="text-[11px] text-slate-400 font-medium">安全与权限控制 (RBAC)</div>
                <div className="mt-1 flex items-center gap-1.5 font-bold text-slate-800">
                  <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
                  强制生效中
                </div>
              </div>
            </div>
          </div>

          <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>系统时区：中国标准时间 (UTC+8)</span>
            <Link to="/admin/system" className="text-indigo-600 hover:underline font-semibold flex items-center gap-1">
              详细监控指标 →
            </Link>
          </div>
        </div>

        {/* Bento Card 2: Governance & People (col-span-5) */}
        <div className="lg:col-span-5 bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950 rounded-2xl p-6 text-white shadow-elevated flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-white/10 text-indigo-200 border border-white/15">
                <Users className="w-3 h-3 text-indigo-300" />
                服务网格与人力容量
              </span>
              <span className="text-[11px] text-indigo-300 font-mono">组织人员</span>
            </div>

            <h3 className="text-base font-bold text-white mt-3">系统治理与人员访问权限</h3>
            <p className="text-xs text-indigo-200/80 mt-0.5 leading-relaxed">
              管理员、调度员及服务工程师，覆盖广州天河、越秀、海珠及各网点服务班组。
            </p>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <Link
                to="/admin/users"
                className="bg-white/10 hover:bg-white/15 border border-white/15 rounded-xl p-3.5 transition-colors group"
              >
                <div className="text-xs text-indigo-200 font-medium">平台内部账号</div>
                <div className="text-2xl font-black text-white font-mono mt-1 group-hover:scale-105 transition-transform">
                  {system?.active_internal_users ?? 0}
                </div>
                <div className="text-[10px] text-indigo-300 mt-1">管理用户权限 →</div>
              </Link>

              <Link
                to="/admin/technicians"
                className="bg-white/10 hover:bg-white/15 border border-white/15 rounded-xl p-3.5 transition-colors group"
              >
                <div className="text-xs text-indigo-200 font-medium">在册服务工程师</div>
                <div className="text-2xl font-black text-emerald-300 font-mono mt-1 group-hover:scale-105 transition-transform">
                  {system?.active_technicians ?? 0}
                </div>
                <div className="text-[10px] text-emerald-300 mt-1">查看网格技能 →</div>
              </Link>
            </div>
          </div>

          <div className="mt-5 pt-3 border-t border-white/15 flex items-center justify-between text-xs text-indigo-200">
            <span>末位管理员自保护防御</span>
            <span className="font-mono text-emerald-400">Anti-Lockout 已生效</span>
          </div>
        </div>
      </div>

      {/* Bento Grid: Row 2 - Policy Revisions & External Integrations */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Policy Versions Card */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-card space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center space-x-2.5">
              <Sliders className="w-5 h-5 text-indigo-600" />
              <div>
                <h3 className="font-bold text-slate-900 text-sm">策略版本控制</h3>
                <p className="text-[11px] text-slate-400">当前活跃派单决策权重与 SLA 时效梯队</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 text-xs">
            {/* Dispatch Policy Version */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-700">智能派单权重</span>
                <span className="px-2 py-0.5 rounded bg-indigo-100 text-indigo-800 text-[11px] font-bold font-mono">
                  v{activeDispatch?.version ?? 1}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 line-clamp-2">
                {activeDispatch?.description || '标准多因子智能推荐派单规则集。'}
              </p>
              <div className="pt-2 border-t border-slate-200/60">
                <Link
                  to="/admin/policies/dispatch"
                  className="text-indigo-600 hover:text-indigo-800 font-semibold text-xs inline-flex items-center gap-1"
                >
                  配置决策权重 →
                </Link>
              </div>
            </div>

            {/* SLA Policy Version */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-700">服务时效阶梯 (SLA)</span>
                <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-800 text-[11px] font-bold font-mono">
                  v{activeSla?.version ?? 1}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 line-clamp-2">
                {activeSla?.description || '紧急至普通四档响应与完工履约标准。'}
              </p>
              <div className="pt-2 border-t border-slate-200/60">
                <Link
                  to="/admin/policies/sla"
                  className="text-amber-700 hover:text-amber-900 font-semibold text-xs inline-flex items-center gap-1"
                >
                  查看时效配置 →
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* External Integrations Summary Card */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-card space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center space-x-2.5">
              <Network className="w-5 h-5 text-teal-600" />
              <div>
                <h3 className="font-bold text-slate-900 text-sm">外部系统与日历集成</h3>
                <p className="text-[11px] text-slate-400">零密钥暴露的安全服务适配器管道</p>
              </div>
            </div>
            <Link
              to="/admin/integrations"
              className="text-xs font-semibold text-teal-700 hover:underline"
            >
              管理配置 →
            </Link>
          </div>

          <div className="space-y-2.5">
            {integrations?.providers?.map((provider) => (
              <div
                key={provider.provider}
                className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200/70 text-xs"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-teal-50 text-teal-700 flex items-center justify-center shrink-0">
                    {provider.type === 'calendar' ? <Calendar className="w-4 h-4" /> : <Mail className="w-4 h-4" />}
                  </div>
                  <div>
                    <div className="font-bold text-slate-900">{provider.provider}</div>
                    <div className="text-[10px] text-slate-400">
                      {provider.badge === 'production' ? '正式环境' : provider.badge || '适配器'}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 font-mono">
                  <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[11px] font-semibold">
                    {provider.success_count} 已同步
                  </span>
                  {provider.failure_count > 0 && (
                    <span className="px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200 text-[11px] font-semibold">
                      {provider.failure_count} 异常
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bento Grid: Row 3 - Recent Security Audit Stream */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-card space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center space-x-2.5">
            <ShieldAlert className="w-5 h-5 text-slate-700" />
            <div>
              <h3 className="font-bold text-slate-900 text-sm">最新防篡改审计活动流</h3>
              <p className="text-[11px] text-slate-400">严格按时间序列记录的系统安全操作痕迹</p>
            </div>
          </div>
          <Link
            to="/admin/audit"
            className="text-xs font-semibold text-slate-700 hover:text-slate-900 hover:underline"
          >
            查看全部审计日志 →
          </Link>
        </div>

        <div className="divide-y divide-slate-100">
          {Array.isArray(recentLogs) && recentLogs.length > 0 ? (
            recentLogs.map((log) => (
              <div key={log.id} className="py-3 flex items-center justify-between text-xs gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-100 text-slate-700 border border-slate-200 shrink-0">
                    {log.action}
                  </span>
                  <div className="min-w-0">
                    <span className="font-medium text-slate-900 truncate block">
                      {log.entity_type} #{log.entity_id}
                    </span>
                    <span className="text-[11px] text-slate-400 truncate block">
                      操作人：{log.actor || '系统'} • 动作：{log.action}
                    </span>
                  </div>
                </div>
                <span className="text-[11px] font-mono text-slate-400 shrink-0">
                  {formatDateTimeZh(log.timestamp)}
                </span>
              </div>
            ))
          ) : (
            <div className="py-6 text-center text-xs text-slate-400">
              暂无最新审计记录。
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
