import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { fetchServiceRequests } from '../api/serviceRequests';
import {
  StatusBadge,
  TableSkeleton,
  ErrorState,
  EmptyState,
  Drawer,
  Button,
} from '../components/ui';
import { formatDateTimeZh } from '../utils/dateTime';
import { ServiceRequestListItem } from '../types/api';
import {
  Filter,
  RefreshCw,
  ClipboardList,
  ExternalLink,
  User,
  MapPin,
  Clock,
  ArrowUpRight,
  LayoutList,
  Map,
} from 'lucide-react';
import { operator } from '../locales/zh-CN/operator';
import { getServiceTypeText } from '../locales';
import { DispatchMapView } from '../components/operator/DispatchMapView';

export const ServiceRequestsPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedRequest, setSelectedRequest] = useState<ServiceRequestListItem | null>(null);
  const [viewMode, setViewMode] = useState<'table' | 'map'>('table');
  const t = operator.requests;

  // URL searchParams as the single source of truth for filter state
  const statusFilter = searchParams.get('status') || 'all';
  const urgencyFilter = searchParams.get('urgency') || 'all';

  const {
    data: requests,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['service-requests', statusFilter, urgencyFilter],
    queryFn: () =>
      fetchServiceRequests({
        status: statusFilter,
        urgency: urgencyFilter,
      }),
  });

  const handleStatusChange = (val: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (val === 'all') next.delete('status');
      else next.set('status', val);
      return next;
    });
  };

  const handleUrgencyChange = (val: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (val === 'all') next.delete('urgency');
      else next.set('urgency', val);
      return next;
    });
  };

  const clearFilters = () => {
    setSearchParams(new URLSearchParams());
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{t.pageTitle}</h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            {t.pageSubtitle}
          </p>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          {/* View Mode Switcher */}
          <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setViewMode('table')}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                viewMode === 'table'
                  ? 'bg-white text-indigo-700 shadow-2xs font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <LayoutList className="w-3.5 h-3.5" />
              <span>表格视图</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode('map')}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                viewMode === 'map'
                  ? 'bg-indigo-600 text-white shadow-2xs font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Map className="w-3.5 h-3.5" />
              <span>GIS 调度地图</span>
            </button>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            isLoading={isFetching}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            {t.refreshBtn}
          </Button>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-card flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span>{t.filters.statusLabel}</span>
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => handleStatusChange(e.target.value)}
            className="text-xs rounded-lg border-slate-300 border bg-white py-1.5 pl-2.5 pr-8 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700 font-medium cursor-pointer"
          >
            <option value="all">{t.filters.allStatuses}</option>
            <option value="waiting_for_approval">待人工确认派单 (waiting_for_approval)</option>
            <option value="ready_for_review">待评估分诊 (ready_for_review)</option>
            <option value="scheduled">已锁定排期 (scheduled)</option>
            <option value="conflict">改期协商中 (conflict)</option>
            <option value="completed">已完工闭环 (completed)</option>
            <option value="rejected">已驳回 (rejected)</option>
            <option value="cancelled">已取消 (cancelled)</option>
          </select>

          {/* Urgency Filter */}
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 ml-2">
            <span>{t.filters.urgencyLabel}</span>
          </div>
          <select
            value={urgencyFilter}
            onChange={(e) => handleUrgencyChange(e.target.value)}
            className="text-xs rounded-lg border-slate-300 border bg-white py-1.5 pl-2.5 pr-8 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700 font-medium cursor-pointer"
          >
            <option value="all">{t.filters.allUrgencies}</option>
            <option value="emergency">紧急 (Emergency)</option>
            <option value="high">高 (High)</option>
            <option value="medium">普通 (Medium)</option>
            <option value="low">低 (Low)</option>
          </select>

          {(statusFilter !== 'all' || urgencyFilter !== 'all') && (
            <button
              onClick={clearFilters}
              className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold underline ml-1 cursor-pointer"
            >
              重置筛选
            </button>
          )}
        </div>

        <div className="text-xs text-slate-400 font-medium">
          共计 {requests?.length ?? 0} 笔工单
        </div>
      </div>

      {/* Content Area */}
      {isLoading ? (
        <TableSkeleton rows={8} />
      ) : isError ? (
        <ErrorState
          title="加载工单列表失败"
          message={(error as any)?.message || '获取工单数据时发生异常，请重试。'}
          onRetry={() => refetch()}
        />
      ) : !requests || requests.length === 0 ? (
        <EmptyState
          icon={<ClipboardList className="h-6 w-6" />}
          title="未找到符合条件的工单"
          description="当前筛选条件下暂无服务工单。"
          action={
            (statusFilter !== 'all' || urgencyFilter !== 'all') && (
              <Button variant="outline" size="sm" onClick={clearFilters}>
                清除所有筛选条件
              </Button>
            )
          }
        />
      ) : viewMode === 'map' ? (
        <DispatchMapView
          requests={requests}
          onSelectRequest={(sr) => setSelectedRequest(sr)}
        />
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50/80 sticky top-0 z-10 backdrop-blur-xs text-slate-500 font-semibold uppercase tracking-wider">
                <tr>
                  <th scope="col" className="px-5 py-3.5">
                    {t.table.id}
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    {t.table.customer}
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    {t.table.serviceType} / {t.table.location}
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    {t.table.urgency}
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    服务时效
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    {t.table.status}
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    {t.table.createdAt}
                  </th>
                  <th scope="col" className="px-5 py-3.5 text-right">
                    {t.table.actions}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {requests.map((sr) => (
                  <tr
                    key={sr.id}
                    onClick={() => setSelectedRequest(sr)}
                    className="hover:bg-slate-50/80 cursor-pointer transition-colors"
                  >
                    <td className="px-5 py-3.5 font-mono font-bold text-slate-900">
                      #{sr.id}
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="font-semibold text-slate-900">{sr.customer_name}</div>
                      <div className="text-[11px] text-slate-400 truncate max-w-[140px]">
                        {sr.customer_email || sr.customer_phone || '未提供直接联系方式'}
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="font-medium text-slate-800">{getServiceTypeText(sr.service_type)}</div>
                      <div className="text-[11px] text-slate-500">{sr.location || '待确认位置'}</div>
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge type="urgency" value={sr.urgency} />
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge type="sla" value={sr.sla_status} />
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge type="status" value={sr.status} />
                    </td>
                    <td className="px-5 py-3.5 font-mono text-slate-500 text-[11px]">
                      {formatDateTimeZh(sr.created_at)}
                    </td>
                    <td className="px-5 py-3.5 text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => setSelectedRequest(sr)}
                          className="px-2.5 py-1 text-xs font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-md transition-colors cursor-pointer"
                        >
                          预览
                        </button>
                        <Link
                          to={`/service-requests/${sr.id}`}
                          className="p-1 text-slate-400 hover:text-slate-700 transition-colors"
                          title="查看完整详情"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Quick Preview Side Drawer */}
      <Drawer
        isOpen={!!selectedRequest}
        onClose={() => setSelectedRequest(null)}
        title={selectedRequest ? `工单详情 #${selectedRequest.id}` : '工单快速预览'}
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
                进入完整工单详情
              </Button>
            </>
          )
        }
      >
        {selectedRequest && (
          <div className="space-y-6">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-3 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-500 font-medium">SLA 服务时效</span>
                <StatusBadge type="sla" value={selectedRequest.sla_status} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500 font-medium">紧急程度</span>
                <StatusBadge type="urgency" value={selectedRequest.urgency} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500 font-medium">报修分类</span>
                <span className="font-semibold text-slate-800">
                  {getServiceTypeText(selectedRequest.service_type)}
                </span>
              </div>
            </div>

            <div>
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                报修客户基本信息
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

            <div>
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                客户原始报修诉求
              </h4>
              <div className="bg-slate-50 rounded-xl border border-slate-200 p-4 text-xs text-slate-700 leading-relaxed font-sans">
                {selectedRequest.raw_message || '客户未填写附加描述。'}
              </div>
            </div>

            {selectedRequest.status === 'waiting_for_approval' && (
              <div className="p-4 rounded-xl bg-purple-50 border border-purple-200 text-purple-900 text-xs flex items-start gap-3">
                <Clock className="w-4 h-4 text-purple-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold">待人工确认派单</div>
                  <div className="text-purple-700 mt-0.5">
                    系统已智能推荐工程师候选人与建议上门时段，等待调度员人工核准。
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
