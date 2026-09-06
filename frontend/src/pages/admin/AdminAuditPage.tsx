import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  FileText,
  Search,
  Filter,
  ShieldCheck,
  ChevronDown,
  ChevronRight,
  Clock,
  User,
  RefreshCw,
} from 'lucide-react';
import { getAuditLogs } from '../../api/adminApi';
import { AuditLogEntry } from '../../types/admin';
import { formatDateTimeZh } from '../../utils/dateTime';

const ENTITY_LABELS: Record<string, string> = {
  internal_user: '内部用户',
  technician: '服务工程师',
  dispatch_policy: '派单策略',
  sla_policy: 'SLA策略',
  service_request: '服务工单',
  appointment: '上门预约',
  customer: '报修客户',
};

const ACTION_LABELS: Record<string, string> = {
  created: '新增创建',
  activated: '生效启用',
  updated: '更新配置',
  deactivated: '停用下线',
  role_changed: '角色调整',
  dispatched: '执行派单',
  cancelled: '取消撤回',
  completed: '完工验收',
  reassigned: '改派工程师',
  acknowledged: '认领响应',
};

export const AdminAuditPage: React.FC = () => {
  const [entityType, setEntityType] = useState<string>('');
  const [actionQuery, setActionQuery] = useState<string>('');
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const { data: logs, isLoading, refetch } = useQuery({
    queryKey: ['admin-audit-logs', entityType, actionQuery],
    queryFn: () =>
      getAuditLogs({
        entity_type: entityType || undefined,
        action: actionQuery || undefined,
        limit: 100,
      }),
  });

  const getActorTypeZh = (type?: string) => {
    switch (type) {
      case 'admin':
        return '管理员';
      case 'operator':
        return '调度员';
      case 'technician':
        return '工程师';
      case 'customer':
        return '客户';
      case 'system':
      default:
        return '系统自动';
    }
  };

  return (
    <div className="space-y-6">
      {/* 头部标题与刷新 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">系统安全与管理审计流水</h1>
          <p className="text-sm text-slate-500 mt-1">
            只读追加存储所有人员操作、策略生效、派单变更与服务流转全链路审计证据。
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 font-medium text-sm rounded-lg shadow-xs transition-colors flex items-center gap-2 self-start sm:self-auto cursor-pointer"
        >
          <RefreshCw className="w-4 h-4 text-slate-500" />
          刷新审计记录
        </button>
      </div>

      {/* 只读不可篡改安全保障横幅 */}
      <div className="p-4 rounded-xl bg-slate-900 text-slate-200 text-xs flex items-center justify-between border border-slate-800 shadow-sm">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center flex-shrink-0">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="font-bold text-white text-sm">不可篡改只读审计保全</div>
            <div className="text-slate-400 mt-0.5 leading-relaxed">
              此审计日志严格采用 Append-Only 仅追加模式落盘存储。任何管理或运维账号均无权修改、截断或删除已有审计记录，确保合规追溯链路的法律与管理严肃性。
            </div>
          </div>
        </div>
      </div>

      {/* 筛选与搜索工具条 */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col sm:flex-row items-center gap-3">
        <div className="w-full sm:w-64">
          <label className="block text-[11px] font-semibold text-slate-500 mb-1">业务对象类型筛选</label>
          <select
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
            className="w-full text-xs bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-700 focus:outline-none focus:ring-1 focus:ring-amber-500"
          >
            <option value="">全部业务实体</option>
            <option value="internal_user">内部用户 (internal_user)</option>
            <option value="technician">服务工程师 (technician)</option>
            <option value="dispatch_policy">智能派单策略 (dispatch_policy)</option>
            <option value="sla_policy">SLA 时效策略 (sla_policy)</option>
            <option value="service_request">服务报修工单 (service_request)</option>
            <option value="appointment">上门预约单 (appointment)</option>
            <option value="customer">报修客户 (customer)</option>
          </select>
        </div>

        <div className="w-full sm:flex-1">
          <label className="block text-[11px] font-semibold text-slate-500 mb-1">搜索操作行为 / 关键词</label>
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={actionQuery}
              onChange={(e) => setActionQuery(e.target.value)}
              placeholder="输入行为关键词，例如：created, activated, role_changed..."
              className="w-full pl-9 pr-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-amber-500"
            >
            </input>
          </div>
        </div>
      </div>

      {/* 审计日志明细表格 */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">发生时间</th>
                <th className="px-6 py-3.5">关联业务实体</th>
                <th className="px-6 py-3.5">操作类型</th>
                <th className="px-6 py-3.5">执行操作人</th>
                <th className="px-6 py-3.5 text-right">变更载荷明细</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-sans">
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-400">
                    正在载入审计记录流水...
                  </td>
                </tr>
              ) : Array.isArray(logs) && logs.length > 0 ? (
                logs.map((entry) => {
                  const isExpanded = expandedId === entry.id;
                  const entityLabel = ENTITY_LABELS[entry.entity_type] || entry.entity_type;
                  const actionLabel = ACTION_LABELS[entry.action] || entry.action;

                  return (
                    <React.Fragment key={entry.id}>
                      <tr
                        onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                        className="hover:bg-slate-50/60 transition-colors cursor-pointer"
                      >
                        <td className="px-6 py-3.5 text-xs text-slate-500 whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <Clock className="w-3.5 h-3.5 text-slate-400" />
                            {formatDateTimeZh(entry.timestamp)}
                          </div>
                        </td>
                        <td className="px-6 py-3.5">
                          <span className="inline-flex items-center gap-1 font-mono text-xs font-semibold text-slate-800 bg-slate-100 px-2 py-0.5 rounded">
                            {entityLabel} #{entry.entity_id}
                          </span>
                        </td>
                        <td className="px-6 py-3.5">
                          <span className="text-xs font-medium text-slate-900 bg-amber-50 text-amber-800 border border-amber-200 px-2 py-0.5 rounded">
                            {actionLabel}
                          </span>
                        </td>
                        <td className="px-6 py-3.5 text-xs text-slate-600">
                          <div className="flex items-center gap-1">
                            <User className="w-3 h-3 text-slate-400" />
                            <span className="font-medium text-slate-800">{entry.details?.actor || '系统'}</span>
                            <span className="text-[10px] text-slate-400">
                              ({getActorTypeZh(entry.details?.actor_type)})
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-3.5 text-right">
                          <button
                            type="button"
                            className="text-xs text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-1 cursor-pointer"
                          >
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                            {isExpanded ? '收起载荷' : '查看详情'}
                          </button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="bg-slate-50/70 border-b border-slate-200">
                          <td colSpan={5} className="px-6 py-3">
                            <div className="p-3 bg-slate-900 rounded-lg text-emerald-400 font-mono text-[11px] overflow-x-auto shadow-inner">
                              <pre>{JSON.stringify(entry.details, null, 2)}</pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-400">
                    暂未检索到符合条件的审计日志。
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
