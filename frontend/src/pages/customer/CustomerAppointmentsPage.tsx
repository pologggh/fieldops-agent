import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import * as customerApi from '../../api/customerApi';
import {
  Clock,
  MapPin,
  CheckCircle2,
  ChevronRight,
  Calendar,
  User,
  PlusCircle,
  CalendarClock,
  ArrowRight,
  AlertCircle,
  FileText,
} from 'lucide-react';
import { StatusBadge, Button } from '../../components/ui';
import { formatDateTimeZh, formatTimeRangeZh } from '../../utils/dateTime';
import { t, getServiceTypeText } from '../../locales';

export const CustomerAppointmentsPage: React.FC = () => {
  const [filter, setFilter] = useState('all');
  const navigate = useNavigate();

  const { data: appointments, isLoading, error } = useQuery({
    queryKey: ['customer-appointments', filter],
    queryFn: () => customerApi.fetchCustomerAppointments(filter),
  });

  const getApptDateBlock = (startTimeStr?: string) => {
    if (!startTimeStr) return { month: '预约', day: '--', weekday: '待定' };
    const date = new Date(startTimeStr);
    if (isNaN(date.getTime())) return { month: '预约', day: '--', weekday: '待确认' };
    const month = `${date.getMonth() + 1}月`;
    const day = String(date.getDate()).padStart(2, '0');
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    const weekday = weekdays[date.getDay()];
    return { month, day, weekday };
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pt-1">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            {t.appointments.title}
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            {t.appointments.subtitle}
          </p>
        </div>

        <Link to="/customer/requests/new">
          <Button
            variant="outline"
            size="sm"
            leftIcon={<PlusCircle className="w-4 h-4" />}
          >
            {t.appointments.submitRequestLink}
          </Button>
        </Link>
      </div>

      {/* Filter Tabs */}
      <div className="bg-white p-2 rounded-2xl border border-slate-200/80 shadow-xs flex items-center space-x-1.5 overflow-x-auto">
        {[
          { id: 'all', label: t.appointments.tabs.all },
          { id: 'scheduled', label: t.appointments.tabs.scheduled },
          { id: 'completed', label: t.appointments.tabs.completed },
          { id: 'cancelled', label: t.appointments.tabs.cancelled },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setFilter(tab.id)}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
              filter === tab.id
                ? 'bg-emerald-600 text-white shadow-xs'
                : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Appointments List / Grid */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="bg-white rounded-2xl border border-slate-200/80 p-12 text-center text-xs text-slate-400">
            {t.appointments.loading}
          </div>
        ) : error ? (
          <div className="bg-white rounded-2xl border border-rose-200 p-12 text-center text-xs text-rose-600">
            {t.appointments.loadError}
          </div>
        ) : !appointments || appointments.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200/80 p-12 text-center space-y-3 shadow-xs">
            <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 mx-auto flex items-center justify-center">
              <CalendarClock className="w-6 h-6" />
            </div>
            <p className="text-xs font-medium text-slate-600">{t.appointments.emptyList}</p>
            <p className="text-[11px] text-slate-400 max-w-sm mx-auto">
              工单派发并经工程师接单确认后，将自动在此生成上门预约与详细行程。
            </p>
            <Link
              to="/customer/requests/new"
              className="mt-2 inline-flex items-center text-xs font-bold text-emerald-600 hover:underline"
            >
              {t.appointments.submitRequestLink} →
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {appointments.map((appt) => {
              const dateBlock = getApptDateBlock(appt.start_time);
              return (
                <div
                  key={appt.id}
                  onClick={() => navigate(`/customer/appointments/${appt.id}`)}
                  className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-xs hover:shadow-md hover:border-emerald-200/90 transition-all cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-4 group"
                >
                  <div className="flex items-start gap-4 min-w-0">
                    {/* Date Block */}
                    <div className="shrink-0 text-center bg-slate-50 group-hover:bg-emerald-50/50 rounded-xl px-3.5 py-2.5 border border-slate-200/70 group-hover:border-emerald-200/80 transition-colors">
                      <div className="text-[10px] font-bold text-emerald-800 uppercase tracking-wider">
                        {dateBlock.month}
                      </div>
                      <div className="text-2xl font-black text-slate-900 leading-none my-0.5">
                        {dateBlock.day}
                      </div>
                      <div className="text-[10px] font-medium text-slate-500">
                        {dateBlock.weekday}
                      </div>
                    </div>

                    {/* Information */}
                    <div className="space-y-1.5 min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-mono font-medium text-slate-400">
                          {t.appointments.visitPrefix.replace('{id}', String(appt.id))}
                        </span>
                        <span className="text-sm font-bold text-slate-900 group-hover:text-emerald-700 transition-colors">
                          {getServiceTypeText(appt.service_type)}
                        </span>
                        <StatusBadge type="status" value={appt.status} locale="zh" />
                      </div>

                      <div className="text-xs text-slate-600 flex flex-wrap items-center gap-y-1 gap-x-4">
                        <div className="flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span className="font-mono">{formatTimeRangeZh(appt.start_time, appt.end_time)}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <User className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                          <span>{t.appointments.specialistLabel}<strong>{appt.technician_name}</strong></span>
                        </div>
                      </div>

                      {appt.location && (
                        <div className="text-xs text-slate-400 flex items-center gap-1.5 pt-0.5">
                          <MapPin className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate">{appt.location}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right Action */}
                  <div className="flex items-center justify-end sm:justify-center gap-2 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100">
                    <span className="text-xs font-bold text-emerald-600 group-hover:underline">
                      {t.appointments.viewBtn}
                    </span>
                    <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-emerald-600 group-hover:translate-x-0.5 transition-all" />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
