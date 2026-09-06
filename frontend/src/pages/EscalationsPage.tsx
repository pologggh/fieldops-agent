import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { fetchEscalations } from '../api/escalations';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorMessage } from '../components/common/ErrorMessage';
import { EmptyState } from '../components/common/EmptyState';
import { formatDateTimeZh } from '../utils/dateTime';
import { Filter, RefreshCw, Eye, AlertOctagon } from 'lucide-react';

export const EscalationsPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const severityFilter = searchParams.get('severity') || 'all';
  const statusFilter = searchParams.get('status') || 'all';

  const {
    data: escalations,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['escalations', severityFilter, statusFilter],
    queryFn: () =>
      fetchEscalations({
        severity: severityFilter,
        status: statusFilter,
      }),
  });

  const handleSeverityChange = (val: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (val === 'all') next.delete('severity');
      else next.set('severity', val);
      return next;
    });
  };

  const handleStatusChange = (val: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (val === 'all') next.delete('status');
      else next.set('status', val);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">升级处理中心</h1>
          <p className="text-sm text-slate-500 mt-1">
            监控服务时效超期、派单冲突与客户严重故障，需调度员立即人工干预协同。
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center px-3.5 py-2 border border-slate-300 shadow-sm text-xs font-semibold rounded-lg text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 self-start sm:self-auto cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isFetching ? 'animate-spin' : ''}`} />
          刷新数据
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span>筛选条件：</span>
          </div>

          <select
            value={severityFilter}
            onChange={(e) => handleSeverityChange(e.target.value)}
            className="text-xs rounded-lg border-slate-300 border bg-white py-1.5 pl-2.5 pr-8 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700 cursor-pointer"
          >
            <option value="all">全部严重级别</option>
            <option value="critical">严重 (Critical)</option>
            <option value="high">高 (High)</option>
            <option value="medium">中 (Medium)</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => handleStatusChange(e.target.value)}
            className="text-xs rounded-lg border-slate-300 border bg-white py-1.5 pl-2.5 pr-8 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700 cursor-pointer"
          >
            <option value="all">全部处理状态</option>
            <option value="open">待处理 (Open)</option>
            <option value="acknowledged">已确认响应 (Acknowledged)</option>
            <option value="resolved">已解决闭环 (Resolved)</option>
          </select>
        </div>

        <div className="text-xs text-slate-400 font-medium">
          共计 {escalations?.length ?? 0} 起升级事件
        </div>
      </div>

      {/* Content Area */}
      {isLoading ? (
        <LoadingSpinner label="正在加载升级工单数据…" className="py-20" />
      ) : isError ? (
        <ErrorMessage
          title="加载升级记录失败"
          message={(error as any)?.message || '获取升级数据时发生异常，请重试。'}
          onRetry={() => refetch()}
        />
      ) : !escalations || escalations.length === 0 ? (
        <EmptyState
          icon={<AlertOctagon className="h-6 w-6 text-emerald-500" />}
          title="暂无活跃的升级工单"
          description="全域工单流转顺畅，未发生 SLA 履约超期或调度冲突。"
        />
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider">
                <tr>
                  <th scope="col" className="px-5 py-3.5">
                    升级编号
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    报修客户
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    升级原因与说明
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    严重级别
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    服务时效
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    处理状态
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    触发时间 (UTC+8)
                  </th>
                  <th scope="col" className="px-5 py-3.5 text-right">
                    调度操作
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {escalations.map((esc) => (
                  <tr
                    key={esc.id}
                    onClick={() => navigate(`/escalations/${esc.id}`)}
                    className="hover:bg-indigo-50/40 cursor-pointer transition-colors"
                  >
                    <td className="px-5 py-3.5 font-mono font-semibold text-rose-600">
                      #{esc.id}
                    </td>
                    <td className="px-5 py-3.5 font-semibold text-slate-900">
                      {esc.customer_name}
                    </td>
                    <td className="px-5 py-3.5 text-slate-700 max-w-xs truncate">
                      {esc.reason}
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge type="severity" value={esc.severity} />
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge type="sla" value={esc.sla_status} />
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge type="status" value={esc.status} />
                    </td>
                    <td className="px-5 py-3.5 text-slate-500 whitespace-nowrap font-mono">
                      {formatDateTimeZh(esc.created_at)}
                    </td>
                    <td
                      className="px-5 py-3.5 text-right whitespace-nowrap"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Link
                        to={`/escalations/${esc.id}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-slate-200 text-slate-700 bg-white hover:bg-slate-50 hover:border-slate-300 font-medium text-xs transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5 text-slate-400" />
                        处理升级
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
