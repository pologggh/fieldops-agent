import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import * as customerApi from '../../api/customerApi';
import {
  PlusCircle,
  Search,
  Clock,
  MapPin,
  ChevronRight,
  Sparkles,
  Wrench,
  Zap,
  Droplets,
  FileText,
  Calendar,
  X,
} from 'lucide-react';
import { StatusBadge, Button } from '../../components/ui';
import { formatDateTimeZh } from '../../utils/dateTime';
import { t, getServiceTypeText } from '../../locales';
import { useSwipeGesture } from '../../hooks/useSwipeGesture';

export const CustomerRequestsPage: React.FC = () => {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const navigate = useNavigate();

  const TABS = [
    { id: 'all', label: t.myRequests.tabs.all },
    { id: 'needs_information', label: t.myRequests.tabs.needs_information },
    { id: 'scheduled', label: t.myRequests.tabs.scheduled },
    { id: 'completed', label: t.myRequests.tabs.completed },
    { id: 'cancelled', label: t.myRequests.tabs.cancelled },
  ];

  const currentTabIndex = TABS.findIndex((tab) => tab.id === filter);

  const handleSwipeLeft = () => {
    const nextIndex = currentTabIndex < TABS.length - 1 ? currentTabIndex + 1 : 0;
    setFilter(TABS[nextIndex].id);
  };

  const handleSwipeRight = () => {
    const prevIndex = currentTabIndex > 0 ? currentTabIndex - 1 : TABS.length - 1;
    setFilter(TABS[prevIndex].id);
  };

  const swipeHandlers = useSwipeGesture({
    onSwipeLeft: handleSwipeLeft,
    onSwipeRight: handleSwipeRight,
    minDistance: 45,
  });

  const { data: requests, isLoading, error } = useQuery({
    queryKey: ['customer-requests', filter],
    queryFn: () => customerApi.fetchCustomerRequests(filter),
  });

  const getCategoryIcon = (serviceType?: string) => {
    const st = (serviceType || '').toLowerCase();
    if (st.includes('plumb') || st.includes('leak') || st.includes('水')) {
      return <Droplets className="w-4 h-4 text-sky-600" />;
    }
    if (st.includes('elect') || st.includes('wire') || st.includes('电')) {
      return <Zap className="w-4 h-4 text-amber-600" />;
    }
    if (st.includes('hvac') || st.includes('air') || st.includes('空调') || st.includes('暖通')) {
      return <Wrench className="w-4 h-4 text-indigo-600" />;
    }
    return <FileText className="w-4 h-4 text-slate-600" />;
  };

  const filteredRequests = (requests || []).filter((r) => {
    if (!search.trim()) return true;
    const term = search.toLowerCase();
    const serviceTypeZh = getServiceTypeText(r.service_type).toLowerCase();
    return (
      r.service_type.toLowerCase().includes(term) ||
      serviceTypeZh.includes(term) ||
      r.problem_description.toLowerCase().includes(term) ||
      (r.location && r.location.toLowerCase().includes(term)) ||
      r.id.toString().includes(term)
    );
  });

  return (
    <div
      {...swipeHandlers}
      className="space-y-6 max-w-5xl mx-auto pb-12 select-none sm:select-auto touch-pan-y"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pt-1">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            {t.myRequests.title}
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            {t.myRequests.subtitle}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Link to="/customer/assistant">
            <Button
              variant="primary"
              size="sm"
              leftIcon={<Sparkles className="w-3.5 h-3.5" />}
              className="bg-indigo-600 hover:bg-indigo-700"
            >
              使用 AI 申报
            </Button>
          </Link>
          <Link to="/customer/requests/new">
            <Button
              variant="outline"
              size="sm"
              leftIcon={<PlusCircle className="w-3.5 h-3.5" />}
            >
              {t.myRequests.requestServiceBtn}
            </Button>
          </Link>
        </div>
      </div>

      {/* Filter Tabs & Search Bar */}
      <div className="bg-white p-3 sm:p-4 rounded-2xl border border-slate-200/80 shadow-xs flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="w-full sm:w-auto">
          <div className="flex items-center space-x-1.5 overflow-x-auto w-full no-scrollbar pb-0.5">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setFilter(tab.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                  filter === tab.id
                    ? 'bg-indigo-600 text-white shadow-xs'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="sm:hidden text-[10px] text-slate-400 flex items-center justify-center gap-1 pt-1.5 font-medium">
            <span>👈 左右轻扫切换分类 👉</span>
          </div>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder={t.myRequests.searchPlaceholder}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-8 py-1.5 border border-slate-200 rounded-xl text-xs text-slate-900 bg-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-2xs"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Requests List */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="bg-white rounded-2xl border border-slate-200/80 p-12 text-center text-xs text-slate-400">
            {t.myRequests.loading}
          </div>
        ) : error ? (
          <div className="bg-white rounded-2xl border border-rose-200 p-12 text-center text-xs text-rose-600">
            {t.myRequests.loadError}
          </div>
        ) : filteredRequests.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200/80 p-12 text-center space-y-3 shadow-xs">
            <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 mx-auto flex items-center justify-center">
              <FileText className="w-6 h-6" />
            </div>
            <p className="text-xs font-medium text-slate-600">{t.myRequests.emptyList}</p>
            {search ? (
              <button
                onClick={() => setSearch('')}
                className="text-xs font-semibold text-indigo-600 hover:underline"
              >
                清除搜索关键字
              </button>
            ) : (
              <Link
                to="/customer/assistant"
                className="mt-2 inline-flex items-center text-xs font-bold text-indigo-600 hover:underline"
              >
                {t.myRequests.createFirst} →
              </Link>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {filteredRequests.map((req) => (
              <div
                key={req.id}
                onClick={() => navigate(`/customer/requests/${req.id}`)}
                className="bg-white rounded-2xl border border-slate-200/80 p-4 sm:p-5 shadow-xs hover:shadow-md hover:border-indigo-200/90 transition-all cursor-pointer flex items-center justify-between gap-4 group"
              >
                <div className="flex items-start gap-4 min-w-0 flex-1">
                  {/* Category icon */}
                  <div className="w-10 h-10 rounded-xl bg-slate-100 group-hover:bg-indigo-50 transition-colors flex items-center justify-center shrink-0 mt-0.5">
                    {getCategoryIcon(req.service_type)}
                  </div>

                  {/* Info */}
                  <div className="space-y-1 min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-mono font-medium text-slate-400">
                        {t.myRequests.ticketIdPrefix}{req.id}
                      </span>
                      <span className="text-sm font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                        {getServiceTypeText(req.service_type)}
                      </span>
                      <StatusBadge type="status" value={req.customer_status} locale="zh" />
                    </div>

                    <p className="text-xs text-slate-600 line-clamp-1 leading-relaxed">
                      {req.problem_description}
                    </p>

                    <div className="flex flex-wrap items-center text-[11px] text-slate-400 gap-y-1 gap-x-3.5 pt-0.5">
                      {req.location && (
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3 h-3 text-slate-400 shrink-0" />
                          <span className="truncate max-w-[200px]">{req.location}</span>
                        </span>
                      )}
                      {req.submitted_at && (
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3 text-slate-400 shrink-0" />
                          <span>{t.myRequests.submittedAt.replace('{time}', formatDateTimeZh(req.submitted_at))}</span>
                        </span>
                      )}
                      {req.appointment && (
                        <span className="flex items-center gap-1 text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded-md">
                          <Calendar className="w-3 h-3 text-emerald-600" />
                          <span>{t.myRequests.visitAt.replace('{time}', formatDateTimeZh(req.appointment.start_time))}</span>
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center text-slate-300 group-hover:text-indigo-600 group-hover:translate-x-0.5 transition-all shrink-0 pl-2">
                  <ChevronRight className="w-5 h-5" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
