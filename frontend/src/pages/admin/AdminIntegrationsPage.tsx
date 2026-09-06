import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Network,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ShieldCheck,
  Calendar,
  Mail,
  RefreshCw,
} from 'lucide-react';
import { getIntegrationSummary, getIntegrationFailures } from '../../api/adminApi';
import { formatDateTimeZh } from '../../utils/dateTime';

export const AdminIntegrationsPage: React.FC = () => {
  const [providerFilter, setProviderFilter] = useState<string>('');

  const { data: summary, isLoading: isSummaryLoading, refetch: refetchSummary } = useQuery({
    queryKey: ['admin-integration-summary'],
    queryFn: getIntegrationSummary,
  });

  const { data: failures, isLoading: isFailuresLoading, refetch: refetchFailures } = useQuery({
    queryKey: ['admin-integration-failures', providerFilter],
    queryFn: () => getIntegrationFailures(providerFilter || undefined),
  });

  const handleRefresh = () => {
    refetchSummary();
    refetchFailures();
  };

  const getProviderName = (provider: string, type: string) => {
    if (provider.includes('Calendar') || type === 'calendar') {
      return 'Google Calendar 工程师排班日历';
    }
    if (provider.includes('Email') || type === 'email') {
      return '企业邮件通知网关';
    }
    return provider;
  };

  const getProviderTypeZh = (type: string) => {
    switch (type) {
      case 'calendar':
        return '双向日程同步 (模拟环境)';
      case 'email':
        return '消息通知推送 (模拟环境)';
      default:
        return '外部服务集成';
    }
  };

  const getResourceNameZh = (resourceType?: string) => {
    switch (resourceType) {
      case 'appointment':
        return '上门预约单';
      case 'service_request':
        return '服务报修工单';
      case 'technician':
        return '服务工程师日程';
      default:
        return resourceType || '关联资源';
    }
  };

  return (
    <div className="space-y-8">
      {/* 头部标题与刷新 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">外部系统集成与通道状态</h1>
          <p className="text-sm text-slate-500 mt-1">
            实时监控 Google Calendar 工程师排班同步、邮件消息网关、外联通道吞吐及异常重试日志。
          </p>
        </div>
        <button
          onClick={handleRefresh}
          className="px-4 py-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 font-medium text-sm rounded-lg shadow-xs transition-colors flex items-center gap-2 self-start sm:self-auto cursor-pointer"
        >
          <RefreshCw className="w-4 h-4 text-slate-500" />
          刷新集成状态
        </button>
      </div>

      {/* 严格零凭据暴露安全规范横幅 */}
      <div className="p-4 rounded-xl bg-slate-900 text-slate-200 text-xs flex items-center justify-between border border-slate-800 shadow-sm">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center flex-shrink-0">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="font-bold text-white text-sm">严格零凭据暴露安全规范</div>
            <div className="text-slate-400 mt-0.5 leading-relaxed">
              系统严格遵循安全准则：API Token、OAuth 密钥、Webhook 签名及数据库凭证一律不下发至前端或接口响应。此处仅展示各服务通道的可用性遥测、同步吞吐量及脱敏异常摘要。
            </div>
          </div>
        </div>
      </div>

      {/* 服务通道卡片列表 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {Array.isArray(summary?.providers) && summary.providers.map((p) => (
          <div key={p.provider} className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                  {p.type === 'calendar' ? <Calendar className="w-5 h-5" /> : <Mail className="w-5 h-5" />}
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-base">{getProviderName(p.provider, p.type)}</h3>
                  <span className="inline-block mt-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                    {p.badge === 'mocked' ? '本地沙箱模拟' : p.badge}
                  </span>
                </div>
              </div>
              <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                已连通运行
              </span>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-100 grid grid-cols-3 gap-4 text-xs">
              <div>
                <span className="text-slate-400 block text-[11px]">累计同步成功</span>
                <span className="text-lg font-bold text-slate-900 font-mono mt-0.5 block">
                  {p.success_count} 次
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">同步失败次数</span>
                <span className={`text-lg font-bold font-mono mt-0.5 block ${p.failure_count > 0 ? 'text-rose-600' : 'text-slate-900'}`}>
                  {p.failure_count} 次
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">通道工作模式</span>
                <span className="text-xs font-semibold text-slate-700 mt-1.5 block">
                  {getProviderTypeZh(p.type)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 集成同步失败日志表格 */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h3 className="font-bold text-slate-900 text-sm">外部集成异常重试日志</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              审查未完成的外部调用记录及脱敏异常原因摘要。
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <select
              value={providerFilter}
              onChange={(e) => setProviderFilter(e.target.value)}
              className="text-xs bg-slate-50 border border-slate-300 rounded-lg px-3 py-1.5 text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="">全部通道服务</option>
              <option value="FakeCalendarClient">Google Calendar 排班日历</option>
              <option value="FakeEmailClient">企业邮件通知网关</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">关联业务实体</th>
                <th className="px-6 py-3.5">集成通道</th>
                <th className="px-6 py-3.5">重试次数</th>
                <th className="px-6 py-3.5">脱敏异常信息摘要</th>
                <th className="px-6 py-3.5 text-right">最后重试时间</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isFailuresLoading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-400">
                    正在载入集成失败记录...
                  </td>
                </tr>
              ) : Array.isArray(failures) && failures.length > 0 ? (
                failures.map((f) => (
                  <tr key={f.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-mono text-xs font-semibold text-slate-900">
                        {getResourceNameZh(f.resource_type)} #{f.local_resource_id}
                      </div>
                      <div className="text-[11px] text-slate-400">同步记录 ID: #{f.id}</div>
                    </td>
                    <td className="px-6 py-4 text-xs font-medium text-slate-800">
                      {f.provider.includes('Calendar') ? 'Google Calendar' : f.provider.includes('Email') ? '邮件通知网关' : f.provider}
                    </td>
                    <td className="px-6 py-4 text-xs font-mono font-semibold text-slate-700">
                      {f.attempt_count} 次
                    </td>
                    <td className="px-6 py-4 text-xs text-rose-700 font-mono max-w-md truncate">
                      {f.last_error_summary || f.last_error || '未知网络抖动或超时重试'}
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-400 text-right">
                      {formatDateTimeZh(f.updated_at)}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-400">
                    <div className="flex flex-col items-center justify-center space-y-1">
                      <CheckCircle2 className="w-6 h-6 text-emerald-500 mb-1" />
                      <span className="font-semibold text-slate-700">外联通道运转正常</span>
                      <span className="text-xs text-slate-400">所有跨系统事件同步均已顺利完成，无堆积重试或失败任务。</span>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
