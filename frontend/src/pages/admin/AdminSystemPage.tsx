import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Server,
  Database,
  Radio,
  Cpu,
  Inbox,
  ShieldCheck,
  CheckCircle2,
  RefreshCw,
  Sparkles,
  Lock,
} from 'lucide-react';
import { getSystemSummary } from '../../api/adminApi';

export const AdminSystemPage: React.FC = () => {
  const { data: system, isLoading, refetch } = useQuery({
    queryKey: ['admin-system-telemetry'],
    queryFn: getSystemSummary,
  });

  const getHealthStatusZh = (status?: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy':
        return '健康运行';
      case 'ready':
        return '正常就绪';
      case 'degraded':
        return '性能降级';
      default:
        return status || '运行正常';
    }
  };

  const getConnectionStatusZh = (status?: string) => {
    switch (status?.toLowerCase()) {
      case 'connected':
        return '正常连通';
      case 'disconnected':
        return '连接断开';
      default:
        return status || '正常连通';
    }
  };

  return (
    <div className="space-y-8">
      {/* 头部标题与刷新 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">系统底层遥测与基础设施健康度</h1>
          <p className="text-sm text-slate-500 mt-1">
            实时监控核心 API 服务实例、数据库连接池、Redis 分布式缓存及事务性发件箱排队状况。
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 font-medium text-sm rounded-lg shadow-xs transition-colors flex items-center gap-2 self-start sm:self-auto cursor-pointer"
        >
          <RefreshCw className="w-4 h-4 text-slate-500" />
          刷新遥测指标
        </button>
      </div>

      {/* 敏感凭据脱敏安全通知 */}
      <div className="p-4 rounded-xl bg-slate-900 text-slate-200 text-xs flex items-center justify-between border border-slate-800 shadow-sm">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center flex-shrink-0">
            <Lock className="w-4 h-4" />
          </div>
          <div>
            <div className="font-bold text-white text-sm">安全加固遥测与脱敏防护</div>
            <div className="text-slate-400 mt-0.5 leading-relaxed">
              系统严格执行安全基线：数据库密码、Redis 认证串及大模型 API Key 绝不下发至前端状态或响应报文，杜绝敏感密钥泄露风险。
            </div>
          </div>
        </div>
      </div>

      {/* 基础设施节点指标矩阵 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              FastAPI 核心服务
            </span>
            <Server className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-3 flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-lg font-bold text-slate-900">
              {getHealthStatusZh(system?.health_status)}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            就绪探针：{getHealthStatusZh(system?.readiness_status)}
          </p>
        </div>

        <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              核心关系数据库
            </span>
            <Database className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-3 flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span className="text-lg font-bold text-slate-900">
              {getConnectionStatusZh(system?.database)}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">PostgreSQL / SQLite (WAL 模式)</p>
        </div>

        <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Redis 消息总线
            </span>
            <Radio className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-3 flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span className="text-lg font-bold text-slate-900">
              {getConnectionStatusZh(system?.redis)}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">速率限制与 Celery 异步队列代理</p>
        </div>

        <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              事务发件箱积压
            </span>
            <Inbox className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-3 flex items-center gap-2">
            <span className="text-2xl font-bold text-slate-900 font-mono">
              {system?.pending_outbox_events ?? 0}
            </span>
            <span className="text-xs text-slate-500">条待投递</span>
          </div>
          <p className="text-xs text-slate-400 mt-1">Transactional Outbox 最终一致性缓冲</p>
        </div>
      </div>

      {/* 大模型决策引擎配置卡片 */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center space-x-3">
            <Sparkles className="w-5 h-5 text-indigo-600" />
            <h3 className="font-bold text-slate-900 text-base">智能决策与大语言模型配置 (LLM)</h3>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
            {system?.llm_config?.configured ? '已连接并就绪' : '待命模式'}
          </span>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/60">
            <span className="text-slate-400 block text-[11px]">当前接入供应商</span>
            <span className="text-sm font-bold text-slate-800 uppercase mt-1 block font-mono">
              {system?.llm_config?.provider === 'fake' ? '沙箱模拟 (Sandbox Mock)' : system?.llm_config?.provider || '模拟引擎'}
            </span>
          </div>
          <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/60">
            <span className="text-slate-400 block text-[11px]">主决策基座模型</span>
            <span className="text-sm font-bold text-slate-800 font-mono mt-1 block">
              {system?.llm_config?.model || 'gpt-4o-mini'}
            </span>
          </div>
          <div className="p-4 rounded-lg bg-slate-50 border border-slate-200/60">
            <span className="text-slate-400 block text-[11px]">结构化流转状态机</span>
            <span className="text-sm font-bold text-emerald-700 mt-1 block">
              LangGraph 工作流引擎
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
