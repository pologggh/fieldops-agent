import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { fetchAppointments } from '../api/appointments';
import {
  StatusBadge,
  TableSkeleton,
  ErrorState,
  EmptyState,
  Drawer,
  Button,
} from '../components/ui';
import { formatTimeRangeZh } from '../utils/dateTime';
import { AppointmentListItem } from '../types/api';
import {
  Filter,
  RefreshCw,
  CalendarCheck2,
  ExternalLink,
  User,
  Wrench,
  MapPin,
  ArrowUpRight,
} from 'lucide-react';
import { operator } from '../locales/zh-CN/operator';
import { getServiceTypeText } from '../locales';

export const AppointmentsPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedAppointment, setSelectedAppointment] = useState<AppointmentListItem | null>(null);
  const t = operator.appointments;

  const statusFilter = searchParams.get('status') || 'all';

  const {
    data: appointments,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['appointments', statusFilter],
    queryFn: () => fetchAppointments({ status: statusFilter }),
  });

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
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{t.pageTitle}</h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            {t.pageSubtitle}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          isLoading={isFetching}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          className="self-start sm:self-auto"
        >
          {t.refreshBtn}
        </Button>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-card flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span>{t.filterLabel}</span>
          </div>

          <select
            value={statusFilter}
            onChange={(e) => handleStatusChange(e.target.value)}
            className="text-xs rounded-lg border-slate-300 border bg-white py-1.5 pl-2.5 pr-8 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700 font-medium cursor-pointer"
          >
            <option value="all">{t.allStatuses}</option>
            <option value="scheduled">已锁定预约 (scheduled)</option>
            <option value="in_progress">服务进行中 (in_progress)</option>
            <option value="completed">已竣工验收 (completed)</option>
            <option value="cancelled">已取消预约 (cancelled)</option>
          </select>
        </div>

        <div className="text-xs text-slate-400 font-medium">
          共计 {appointments?.length ?? 0} 条预约记录
        </div>
      </div>

      {/* Content Area */}
      {isLoading ? (
        <TableSkeleton rows={6} />
      ) : isError ? (
        <ErrorState
          title="加载上门预约数据失败"
          message={(error as any)?.message || '获取预约日程时发生异常，请重试。'}
          onRetry={() => refetch()}
        />
      ) : !appointments || appointments.length === 0 ? (
        <EmptyState
          icon={<CalendarCheck2 className="h-6 w-6" />}
          title="未查询到上门预约"
          description="当前筛选条件下暂无已排期的上门任务。"
          action={
            statusFilter !== 'all' && (
              <Button variant="outline" size="sm" onClick={() => handleStatusChange('all')}>
                显示全部预约
              </Button>
            )
          }
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
                    {t.table.window} (UTC+8)
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    {t.table.technician}
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    {t.table.customer} / {t.table.location}
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    {t.table.serviceType}
                  </th>
                  <th scope="col" className="px-5 py-3.5">
                    {t.table.status}
                  </th>
                  <th scope="col" className="px-5 py-3.5 text-right">
                    {t.table.action}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {appointments.map((appt) => (
                  <tr
                    key={appt.id}
                    onClick={() => setSelectedAppointment(appt)}
                    className="hover:bg-slate-50/80 cursor-pointer transition-colors"
                  >
                    <td className="px-5 py-3.5 font-mono font-bold text-slate-900">
                      #{appt.id}
                    </td>
                    <td className="px-5 py-3.5 font-mono text-slate-800 font-medium">
                      {formatTimeRangeZh(appt.start_time, appt.end_time)}
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="font-semibold text-slate-900">{appt.technician_name}</div>
                      <div className="text-[11px] text-slate-400 font-mono">工程师编号：#{appt.technician_id}</div>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="font-medium text-slate-800">{appt.customer_name}</div>
                      <div className="text-[11px] text-slate-500">{appt.location || '待确认地点'}</div>
                    </td>
                    <td className="px-5 py-3.5 text-slate-700">
                      {getServiceTypeText(appt.service_type)}
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge type="status" value={appt.status} />
                    </td>
                    <td className="px-5 py-3.5 text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => setSelectedAppointment(appt)}
                          className="px-2.5 py-1 text-xs font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-md transition-colors cursor-pointer"
                        >
                          预览
                        </button>
                        <Link
                          to={`/appointments/${appt.id}`}
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
        isOpen={!!selectedAppointment}
        onClose={() => setSelectedAppointment(null)}
        title={selectedAppointment ? `上门预约 #${selectedAppointment.id}` : '预约快速预览'}
        badge={
          selectedAppointment && (
            <StatusBadge type="status" value={selectedAppointment.status} />
          )
        }
        footer={
          selectedAppointment && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedAppointment(null)}
              >
                关闭
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  const id = selectedAppointment.id;
                  setSelectedAppointment(null);
                  navigate(`/appointments/${id}`);
                }}
                rightIcon={<ArrowUpRight className="w-3.5 h-3.5" />}
              >
                进入预约调度详情
              </Button>
            </>
          )
        }
      >
        {selectedAppointment && (
          <div className="space-y-6">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-3 text-xs">
              <div>
                <span className="text-slate-500 block mb-1">预约上门时间窗口 (中国标准时间)</span>
                <span className="font-mono font-bold text-slate-900 text-sm">
                  {formatTimeRangeZh(selectedAppointment.start_time, selectedAppointment.end_time)}
                </span>
              </div>
              <div className="pt-2 border-t border-slate-200 flex items-center justify-between">
                <span className="text-slate-500">报修类别</span>
                <span className="font-semibold text-slate-800">
                  {getServiceTypeText(selectedAppointment.service_type)}
                </span>
              </div>
            </div>

            <div>
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                指派服务工程师
              </h4>
              <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-2 text-xs">
                <div className="flex items-center gap-2 text-slate-900 font-semibold">
                  <Wrench className="w-3.5 h-3.5 text-indigo-600" />
                  {selectedAppointment.technician_name}
                </div>
                <div className="text-[11px] text-slate-500 font-mono">
                  工程师工号：#{selectedAppointment.technician_id}
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                客户与服务目的地
              </h4>
              <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-2 text-xs">
                <div className="flex items-center gap-2 text-slate-900 font-semibold">
                  <User className="w-3.5 h-3.5 text-slate-400" />
                  {selectedAppointment.customer_name}
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                  <MapPin className="w-3.5 h-3.5 text-slate-400" />
                  {selectedAppointment.location || '待确认位置'}
                </div>
                <div className="text-[11px] text-slate-500 pt-1 border-t border-slate-100 font-mono">
                  关联工单编号：#{selectedAppointment.service_request_id}
                </div>
              </div>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
};
