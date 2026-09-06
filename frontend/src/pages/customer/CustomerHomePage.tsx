import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useCustomerAuth } from '../../auth/useCustomerAuth';
import * as customerApi from '../../api/customerApi';
import {
  Wrench,
  Calendar,
  Sparkles,
  ArrowRight,
  Clock,
  MapPin,
  CheckCircle2,
  FileText,
  CalendarClock,
  Zap,
  Droplets,
  ChevronRight,
  User,
  ShieldCheck,
  Check,
  Circle,
  HelpCircle,
} from 'lucide-react';
import {
  CardSkeleton,
  StatusBadge,
  Button,
} from '../../components/ui';
import { formatDateTimeZh, formatTimeRangeZh } from '../../utils/dateTime';
import { t, getCustomerCalmStatus, getServiceTypeText, normalizeCustomerStatus } from '../../locales';

export const CustomerHomePage: React.FC = () => {
  const navigate = useNavigate();
  const { customer } = useCustomerAuth();

  const { data: summary, isLoading: isSummaryLoading } = useQuery({
    queryKey: ['customer-summary'],
    queryFn: customerApi.fetchCustomerSummary,
  });

  const { data: recentRequests, isLoading: isRequestsLoading } = useQuery({
    queryKey: ['customer-recent-requests'],
    queryFn: () => customerApi.fetchCustomerRequests('all'),
  });

  const { data: appointments, isLoading: isApptsLoading } = useQuery({
    queryKey: ['customer-recent-appointments'],
    queryFn: () => customerApi.fetchCustomerAppointments('scheduled'),
  });

  const upcomingAppt = appointments && appointments.length > 0 ? appointments[0] : null;
  const activeRequest = recentRequests && recentRequests.length > 0 ? recentRequests[0] : null;

  // Compute active journey step (1 to 5) based on customer status
  const getJourneyStep = (status?: string): number => {
    const s = normalizeCustomerStatus(status);
    switch (s) {
      case 'submitted':
      case 'received':
      case 'created':
        return 1;
      case 'reviewing':
      case 'matched':
      case 'waiting_for_approval':
      case 'assigned':
        return 2;
      case 'scheduled':
      case 'appointment_created':
        return 3;
      case 'in_progress':
        return 4;
      case 'completed':
        return 5;
      default:
        return 1;
    }
  };

  const getDisplayServiceTitle = (type?: string) => {
    const text = getServiceTypeText(type);
    if (text.endsWith('维修') || text.endsWith('维护') || text.endsWith('服务') || text.endsWith('巡检')) {
      return text;
    }
    return `${text} 维修服务`;
  };

  const journeySteps = [
    { num: 1, label: '需求受理' },
    { num: 2, label: '评估派单' },
    { num: 3, label: '排期锁定' },
    { num: 4, label: '上门服务' },
    { num: 5, label: '服务完成' },
  ];

  // Quick prompt suggestions
  const quickPrompts = [
    { label: '❄️ 空调不制冷 / 异常异响', prompt: '空调制冷效果差，开启后有异常响声，需要检查排查。' },
    { label: '💧 水管破裂 / 卫生间漏水', prompt: '卫生间供水管处有明显漏水现象，地面出现积水。' },
    { label: '⚡ 电路跳闸 / 插座无电', prompt: '配电箱总闸跳闸，无法合闸，部分室内插座没有电。' },
    { label: '📅 预约明天下午综合巡检', prompt: '需要预约一名工程师明天下午上门进行设备运行巡检。' },
  ];

  const handlePromptClick = (promptText: string) => {
    navigate(`/customer/assistant?prompt=${encodeURIComponent(promptText)}`);
  };

  // Helper for category icon
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

  // Date block formatting for upcoming appointment
  const getApptDateBlock = (startTimeStr?: string) => {
    if (!startTimeStr) return { month: '即将', day: '安排', weekday: '待定' };
    const date = new Date(startTimeStr);
    if (isNaN(date.getTime())) return { month: '预约', day: '--', weekday: '待确认' };
    const month = `${date.getMonth() + 1}月`;
    const day = String(date.getDate()).padStart(2, '0');
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    const weekday = weekdays[date.getDay()];
    return { month, day, weekday };
  };

  return (
    <div className="space-y-7 max-w-5xl mx-auto pb-12">
      {/* 1. Hero AI Service Command Center Card */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 text-white shadow-xl border border-slate-800/80 p-6 sm:p-8">
        {/* Subtle background ambient light blobs */}
        <div className="absolute -top-24 -right-24 w-96 h-96 bg-indigo-500/15 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-80 h-80 bg-violet-600/15 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          {/* Left Column: Conversational Guidance & Action */}
          <div className="lg:col-span-7 space-y-5">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-indigo-200 text-xs font-medium backdrop-blur-sm">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400 animate-pulse" />
              <span>FieldOps 智能服务中枢 · 7×24h 极速响应</span>
            </div>

            <div className="space-y-2">
              <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight text-white">
                {t.customerHome.greeting.replace('{name}', customer?.name || t.customerHome.defaultName)}
              </h1>
              <p className="text-sm text-slate-300 leading-relaxed max-w-xl">
                无需查找复杂的报修表单，直接用日常语言描述设备问题，AI 将快速识别服务分类、评估紧急度并协助锁定最佳上门时间。
              </p>
            </div>

            {/* Quick Action Prompt Chips */}
            <div className="space-y-2 pt-1">
              <div className="text-xs text-slate-400 font-medium">快速描述常见问题：</div>
              <div className="flex flex-wrap gap-2">
                {quickPrompts.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handlePromptClick(item.prompt)}
                    className="text-xs px-3 py-1.5 rounded-xl bg-slate-800/80 hover:bg-indigo-600/30 border border-slate-700/70 hover:border-indigo-500/50 text-slate-200 hover:text-white transition-all duration-150 text-left shadow-sm backdrop-blur-sm"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Primary Actions */}
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link to="/customer/assistant">
                <Button
                  variant="primary"
                  size="lg"
                  leftIcon={<Sparkles className="w-4 h-4 text-white" />}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold shadow-lg shadow-indigo-900/40 border-0"
                >
                  {t.customerHome.startWithAi}
                </Button>
              </Link>
              <Link to="/customer/requests/new">
                <Button
                  variant="outline"
                  size="lg"
                  className="bg-slate-800/60 hover:bg-slate-800 text-slate-200 border-slate-700/80 hover:text-white"
                >
                  {t.customerHome.requestServiceForm}
                </Button>
              </Link>
            </div>
          </div>

          {/* Right Column: AI Extraction Structure Hologram */}
          <div className="lg:col-span-5 hidden lg:block">
            <div className="rounded-2xl bg-slate-900/90 border border-slate-700/60 p-5 shadow-2xl backdrop-blur-md space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
                  <span className="text-xs font-semibold text-slate-200">AI 实时需求解析引擎</span>
                </div>
                <span className="text-[11px] font-mono text-indigo-400 bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-800/40">
                  ● 智能就绪
                </span>
              </div>

              {/* Sample Extraction Showcase */}
              <div className="space-y-2.5 text-xs">
                <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-800/60 border border-slate-700/50">
                  <span className="text-slate-400 flex items-center gap-1.5">
                    <Wrench className="w-3.5 h-3.5 text-indigo-400" />
                    专业类型
                  </span>
                  <span className="font-semibold text-slate-100">空调 / 暖通 (HVAC)</span>
                </div>
                <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-800/60 border border-slate-700/50">
                  <span className="text-slate-400 flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                    紧急评估
                  </span>
                  <span className="font-semibold text-slate-100">普通 · 24-48h SLA</span>
                </div>
                <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-800/60 border border-slate-700/50">
                  <span className="text-slate-400 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-amber-400" />
                    建议上门
                  </span>
                  <span className="font-semibold text-slate-100">明天下午 14:00 - 17:00</span>
                </div>
              </div>

              <div className="pt-1 flex items-center gap-2 text-[11px] text-slate-400 border-t border-slate-800">
                <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span>精准语义分析，30 秒快速形成可执行工单草稿</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Key Highlights: Active Service Journey & Upcoming Visit */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Active Service Journey Card */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm hover:shadow-md transition-shadow flex flex-col justify-between">
          <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                  <Wrench className="w-4 h-4" />
                </div>
                <div>
                  <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                    {t.customerHome.activeRequestCardTitle}
                  </span>
                  {activeRequest && (
                    <span className="text-xs font-mono text-slate-400 ml-1.5">
                      #{activeRequest.id}
                    </span>
                  )}
                </div>
              </div>
              {activeRequest && (
                <StatusBadge type="status" value={activeRequest.customer_status} locale="zh" />
              )}
            </div>

            {/* Content */}
            {isRequestsLoading ? (
              <div className="py-8 space-y-3">
                <div className="h-5 w-48 bg-slate-100 rounded animate-pulse" />
                <div className="h-4 w-64 bg-slate-100 rounded animate-pulse" />
                <div className="h-16 w-full bg-slate-50 rounded-xl animate-pulse mt-4" />
              </div>
            ) : activeRequest ? (
              <div className="space-y-4">
                <div>
                  <div className="text-base font-bold text-slate-900">
                    {getDisplayServiceTitle(activeRequest.service_type)}
                  </div>
                  <div className="text-xs text-slate-500 flex items-center gap-1.5 mt-1">
                    <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span className="truncate">{activeRequest.location || '待确认地点'}</span>
                    <span className="text-slate-300">•</span>
                    <span>{t.customerHome.submittedOn.replace('{time}', formatDateTimeZh(activeRequest.submitted_at))}</span>
                  </div>
                </div>

                {/* Service Journey Stepper */}
                <div className="pt-2">
                  <div className="text-[11px] font-semibold text-slate-400 mb-2">服务履约进度</div>
                  <div className="relative flex items-center justify-between">
                    {/* Background track */}
                    <div className="absolute top-1/2 left-2 right-2 -translate-y-1/2 h-0.5 bg-slate-100 -z-0" />
                    {/* Active progress track */}
                    {(() => {
                      const currentStep = getJourneyStep(activeRequest.customer_status);
                      const pct = ((currentStep - 1) / (journeySteps.length - 1)) * 100;
                      return (
                        <div
                          className="absolute top-1/2 left-2 -translate-y-1/2 h-0.5 bg-indigo-600 transition-all duration-300 -z-0"
                          style={{ width: `calc(${pct}% - 16px)` }}
                        />
                      );
                    })()}

                    {journeySteps.map((step) => {
                      const currentStep = getJourneyStep(activeRequest.customer_status);
                      const isCompleted = step.num < currentStep;
                      const isCurrent = step.num === currentStep;

                      return (
                        <div key={step.num} className="flex flex-col items-center gap-1 relative z-10">
                          <div
                            className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold transition-all ${
                              isCompleted
                                ? 'bg-indigo-600 text-white shadow-sm'
                                : isCurrent
                                ? 'bg-white border-2 border-indigo-600 text-indigo-600 shadow-md ring-4 ring-indigo-50'
                                : 'bg-white border border-slate-200 text-slate-400'
                            }`}
                          >
                            {isCompleted ? <Check className="w-3 h-3" /> : step.num}
                          </div>
                          <span
                            className={`text-[10px] whitespace-nowrap ${
                              isCurrent
                                ? 'font-bold text-indigo-600'
                                : isCompleted
                                ? 'text-slate-600 font-medium'
                                : 'text-slate-400'
                            }`}
                          >
                            {step.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Calm Status Projection Callout */}
                {(() => {
                  const projection = getCustomerCalmStatus(activeRequest.customer_status);
                  return (
                    <div className={`p-3.5 rounded-xl border ${projection.color} text-xs leading-relaxed`}>
                      <div className="font-bold flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                        {projection.title}
                      </div>
                      <div className="mt-1 opacity-90">{projection.desc}</div>
                    </div>
                  );
                })()}
              </div>
            ) : (
              <div className="py-10 text-center space-y-2">
                <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center">
                  <Wrench className="w-5 h-5" />
                </div>
                <div className="text-xs font-semibold text-slate-600">{t.customerHome.noActiveRequests}</div>
                <p className="text-[11px] text-slate-400 max-w-xs mx-auto">
                  如果您遇到了设备故障或设施报修问题，可随时点击上方按钮向 AI 助手申报。
                </p>
              </div>
            )}
          </div>

          {/* Footer actions */}
          <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
            {activeRequest ? (
              <Link
                to={`/customer/requests/${activeRequest.id}`}
                className="text-indigo-600 font-semibold hover:text-indigo-700 flex items-center gap-1 group"
              >
                <span>{t.customerHome.trackRequest.replace('{id}', String(activeRequest.id))}</span>
                <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
              </Link>
            ) : (
              <Link
                to="/customer/assistant"
                className="text-indigo-600 font-semibold hover:underline"
              >
                {t.customerHome.reportProblem}
              </Link>
            )}
            <Link to="/customer/requests" className="text-slate-400 hover:text-slate-600">
              {t.customerHome.viewHistory}
            </Link>
          </div>
        </div>

        {/* Upcoming Visit Card */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm hover:shadow-md transition-shadow flex flex-col justify-between">
          <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <Calendar className="w-4 h-4" />
                </div>
                <div>
                  <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                    {t.customerHome.upcomingVisitCardTitle}
                  </span>
                  {upcomingAppt && (
                    <span className="text-xs font-mono text-slate-400 ml-1.5">
                      #{upcomingAppt.id}
                    </span>
                  )}
                </div>
              </div>
              {upcomingAppt && (
                <StatusBadge type="status" value={upcomingAppt.status} locale="zh" />
              )}
            </div>

            {/* Content */}
            {isApptsLoading ? (
              <div className="py-8 space-y-3">
                <div className="h-5 w-48 bg-slate-100 rounded animate-pulse" />
                <div className="h-4 w-64 bg-slate-100 rounded animate-pulse" />
                <div className="h-16 w-full bg-slate-50 rounded-xl animate-pulse mt-4" />
              </div>
            ) : upcomingAppt ? (
              <div className="space-y-4">
                <div className="flex items-start gap-4 p-4 rounded-2xl bg-gradient-to-br from-emerald-50/70 to-teal-50/40 border border-emerald-200/70">
                  {/* Big Date Badge */}
                  {(() => {
                    const dateBlock = getApptDateBlock(upcomingAppt.start_time);
                    return (
                      <div className="shrink-0 text-center bg-white rounded-xl px-3 py-2 border border-emerald-200/80 shadow-xs">
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
                    );
                  })()}

                  {/* Visit Details */}
                  <div className="space-y-1.5 min-w-0 flex-1">
                    <div className="text-xs font-semibold text-emerald-800">
                      {t.customerHome.scheduledWindow}
                    </div>
                    <div className="text-sm font-bold text-slate-900 font-mono tracking-tight">
                      {formatTimeRangeZh(upcomingAppt.start_time, upcomingAppt.end_time)}
                    </div>
                    <div className="text-xs text-slate-600 flex items-center gap-1.5 pt-0.5">
                      <User className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                      <span className="truncate">
                        {t.customerHome.assignedSpecialist}：<strong>{upcomingAppt.technician_name}</strong>
                      </span>
                    </div>
                  </div>
                </div>

                <div className="text-xs text-slate-500 flex items-center gap-1.5 px-1">
                  <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span className="truncate">
                    {upcomingAppt.location || '客户指定现场'} • {getServiceTypeText(upcomingAppt.service_type)}
                  </span>
                </div>
              </div>
            ) : (
              <div className="py-10 text-center space-y-2">
                <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center">
                  <CalendarClock className="w-5 h-5" />
                </div>
                <div className="text-xs font-semibold text-slate-600">
                  {t.customerHome.noUpcomingVisits}
                </div>
                <p className="text-[11px] text-slate-400 max-w-xs mx-auto">
                  {t.customerHome.appointmentsAppearNotice}
                </p>
              </div>
            )}
          </div>

          {/* Footer actions */}
          <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
            {upcomingAppt ? (
              <Link
                to={`/customer/appointments/${upcomingAppt.id}`}
                className="text-emerald-700 font-semibold hover:text-emerald-800 flex items-center gap-1 group"
              >
                <span>{t.customerHome.appointmentDetails}</span>
                <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
              </Link>
            ) : (
              <span className="text-slate-400">{t.customerHome.appointmentsAppearNotice}</span>
            )}
            <Link to="/customer/appointments" className="text-slate-400 hover:text-slate-600">
              {t.customerHome.allVisits}
            </Link>
          </div>
        </div>
      </div>

      {/* 3. Recent Service Activity Section */}
      <section className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-slate-400" />
            <h3 className="text-sm font-bold text-slate-900">{t.customerHome.recentRequestsTitle}</h3>
          </div>
          <Link
            to="/customer/requests"
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center gap-1 group"
          >
            <span>{t.customerHome.viewAllRequests} ({recentRequests?.length || 0})</span>
            <ChevronRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
          </Link>
        </div>

        <div className="divide-y divide-slate-100">
          {recentRequests && recentRequests.length > 0 ? (
            recentRequests.slice(0, 4).map((req) => (
              <Link
                key={req.id}
                to={`/customer/requests/${req.id}`}
                className="py-3.5 flex items-center justify-between text-xs hover:bg-slate-50/80 -mx-2 px-3 rounded-xl transition-all group"
              >
                <div className="flex items-center gap-3.5 min-w-0">
                  <div className="w-9 h-9 rounded-xl bg-slate-100/90 group-hover:bg-indigo-50 transition-colors flex items-center justify-center shrink-0">
                    {getCategoryIcon(req.service_type)}
                  </div>
                  <div className="min-w-0">
                    <div className="font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors truncate">
                      {getDisplayServiceTitle(req.service_type)}
                    </div>
                    <div className="text-[11px] text-slate-400 truncate flex items-center gap-1.5 mt-0.5">
                      <span className="font-mono text-slate-500">#{req.id}</span>
                      <span>•</span>
                      <span>{req.location || '待确认地点'}</span>
                      <span>•</span>
                      <span>{formatDateTimeZh(req.submitted_at)}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <StatusBadge type="status" value={req.customer_status} locale="zh" />
                  <ArrowRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-600 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </Link>
            ))
          ) : (
            <div className="py-8 text-center text-xs text-slate-400">
              {t.customerHome.noRequestsPlacedYet}
            </div>
          )}
        </div>
      </section>
    </div>
  );
};
