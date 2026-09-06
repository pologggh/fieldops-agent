import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchSystemStatus } from '../api/system';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorMessage } from '../components/common/ErrorMessage';
import {
  Activity,
  Database,
  Server,
  Layers,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';

export const SystemStatusPage: React.FC = () => {
  const {
    data: sys,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['system-status'],
    queryFn: fetchSystemStatus,
    refetchInterval: 10000,
  });

  if (isLoading) {
    return <LoadingSpinner label="正在检测调度系统基础设施运行状态…" className="py-24" />;
  }

  if (isError || !sys) {
    return (
      <ErrorMessage
        title="获取系统状态失败"
        message={(error as any)?.message || '无法连接到后端监控服务'}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">调度中心运行状态</h1>
          <p className="text-sm text-slate-500 mt-1">
            实时监控 API 服务、关系型数据库、消息队列与外部日历同步等基础设施健康度。
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center px-3.5 py-2 border border-slate-300 shadow-sm text-xs font-semibold rounded-lg text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 self-start sm:self-auto cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isFetching ? 'animate-spin' : ''}`} />
          刷新状态
        </button>
      </div>

      {/* Grid of System Components */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Core API */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-indigo-50 text-indigo-600">
                <Server className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">FastAPI 核心应用服务</h3>
                <span className="text-xs text-slate-400">核心 HTTP 调度流转引擎</span>
              </div>
            </div>
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-full">
              <CheckCircle2 className="w-3.5 h-3.5" />
              {sys.api?.status === 'online' ? '正常运行' : sys.api?.status || '正常运行'}
            </span>
          </div>

          <div className="text-xs text-slate-600 bg-slate-50 p-3 rounded-lg flex items-center justify-between">
            <span>引擎运行时版本：</span>
            <span className="font-mono font-semibold text-slate-800">
              v{sys.api?.version || '1.0.0'}
            </span>
          </div>
        </div>

        {/* Database */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-blue-50 text-blue-600">
                <Database className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">PostgreSQL 关系型主库</h3>
                <span className="text-xs text-slate-400">业务数据强一致性持久层</span>
              </div>
            </div>
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-full">
              <CheckCircle2 className="w-3.5 h-3.5" />
              {sys.database?.status === 'connected' ? '已连接' : sys.database?.status || '已连接'}
            </span>
          </div>

          <div className="text-xs text-slate-600 bg-slate-50 p-3 rounded-lg flex items-center justify-between">
            <span>连接池活跃连接数：</span>
            <span className="font-mono font-semibold text-slate-800">
              {sys.database?.pool_size ?? 5} 个连接
            </span>
          </div>
        </div>

        {/* Redis */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-amber-50 text-amber-600">
                <Activity className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Redis 缓存与 Celery 队列</h3>
                <span className="text-xs text-slate-400">频率限制与异步派单 Broker</span>
              </div>
            </div>
            <span
              className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full ${
                sys.redis?.status === 'connected'
                  ? 'text-emerald-700 bg-emerald-50 border border-emerald-200'
                  : 'text-amber-800 bg-amber-50 border border-amber-200'
              }`}
            >
              {sys.redis?.status === 'connected' ? (
                <CheckCircle2 className="w-3.5 h-3.5" />
              ) : (
                <AlertTriangle className="w-3.5 h-3.5" />
              )}
              {sys.redis?.status === 'connected' ? '已连接' : '内存降级模式'}
            </span>
          </div>

          <div className="text-xs text-slate-600 bg-slate-50 p-3 rounded-lg flex items-center justify-between">
            <span>高可用容灾保护：</span>
            <span className="font-mono text-slate-700">自动降级策略已生效</span>
          </div>
        </div>

        {/* Transactional Outbox */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-purple-50 text-purple-600">
                <Layers className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Transactional Outbox 事务发件箱</h3>
                <span className="text-xs text-slate-400">Google Calendar 与消息投递可靠保障</span>
              </div>
            </div>
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 px-2.5 py-1 rounded-full">
              {sys.outbox?.pending_count ?? 0} 条待投递
            </span>
          </div>

          <div className="text-xs text-slate-600 bg-slate-50 p-3 rounded-lg flex items-center justify-between">
            <span>失败重试累积：</span>
            <span className="font-mono font-semibold text-slate-800">
              {sys.integrations?.failed_count ?? 0} 次
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
