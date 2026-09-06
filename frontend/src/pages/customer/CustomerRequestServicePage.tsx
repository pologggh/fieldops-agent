import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useCustomerAuth } from '../../auth/useCustomerAuth';
import * as customerApi from '../../api/customerApi';
import { ArrowRight, AlertCircle, Sparkles, Wrench, MapPin, Clock, FileText } from 'lucide-react';
import { Button } from '../../components/ui';
import { t, getServiceTypeText } from '../../locales';

const SERVICE_CATEGORY_OPTIONS = [
  'HVAC',
  'Plumbing',
  'Electrical',
  'Networking',
  'Appliance Repair',
  'General Maintenance',
  'Other',
];

export const CustomerRequestServicePage: React.FC = () => {
  const { customer } = useCustomerAuth();
  const navigate = useNavigate();

  const [serviceType, setServiceType] = useState(SERVICE_CATEGORY_OPTIONS[0]);
  const [problemDescription, setProblemDescription] = useState('');
  const [location, setLocation] = useState(customer?.address || '');
  const [preferredTime, setPreferredTime] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!problemDescription.trim()) {
      setError(t.requestServicePage.descRequiredError);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const created = await customerApi.createCustomerRequest({
        service_type: serviceType,
        problem_description: problemDescription,
        location: location.trim() || undefined,
        preferred_time: preferredTime.trim() || undefined,
      });
      navigate(`/customer/requests/${created.id}`);
    } catch (err: any) {
      setError(err.message || '提交服务请求失败，请重试。');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 pb-12">
      <div className="pt-1">
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
          {t.requestServicePage.title}
        </h1>
        <p className="mt-1 text-xs sm:text-sm text-slate-500">
          {t.requestServicePage.subtitle}
        </p>
      </div>

      {/* AI Assistant Promotion Card */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-indigo-50 to-violet-50 border border-indigo-200/80 shadow-xs flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-indigo-600 text-white flex items-center justify-center shrink-0 shadow-xs">
            <Sparkles className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="text-xs font-bold text-slate-900">想更快更简单地报修？</div>
            <p className="text-[11px] text-slate-500 truncate">
              直接向 FieldOps 智能助手描述问题，自动提取类别与上门建议
            </p>
          </div>
        </div>
        <Link to="/customer/assistant" className="shrink-0">
          <Button variant="primary" size="sm" className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold">
            进入 AI 对话
          </Button>
        </Link>
      </div>

      <div className="bg-white p-6 sm:p-8 rounded-3xl border border-slate-200/80 shadow-xs">
        {error && (
          <div className="mb-5 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Service Category */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              {t.requestServicePage.serviceTypeLabel}
            </label>
            <div className="relative">
              <select
                value={serviceType}
                onChange={(e) => setServiceType(e.target.value)}
                className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-xs bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-2xs"
              >
                {SERVICE_CATEGORY_OPTIONS.map((cat) => (
                  <option key={cat} value={cat}>
                    {getServiceTypeText(cat)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Problem Description */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              {t.requestServicePage.problemDescLabel}
            </label>
            <textarea
              required
              rows={4}
              value={problemDescription}
              onChange={(e) => setProblemDescription(e.target.value)}
              placeholder={t.requestServicePage.problemPlaceholder}
              className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-xs text-slate-900 bg-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-2xs leading-relaxed"
            />
          </div>

          {/* Location */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              {t.requestServicePage.locationLabel}
            </label>
            <div className="relative">
              <MapPin className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder={t.requestServicePage.locationPlaceholder}
                className="w-full pl-10 pr-3.5 py-2.5 border border-slate-300 rounded-xl text-xs text-slate-900 bg-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-2xs"
              />
            </div>
            <p className="mt-1 text-[11px] text-slate-400">
              {t.requestServicePage.locationHint}
            </p>
          </div>

          {/* Preferred Time */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              {t.requestServicePage.preferredTimeLabel}
            </label>
            <div className="relative">
              <Clock className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
              <input
                type="text"
                value={preferredTime}
                onChange={(e) => setPreferredTime(e.target.value)}
                placeholder={t.requestServicePage.preferredTimePlaceholder}
                className="w-full pl-10 pr-3.5 py-2.5 border border-slate-300 rounded-xl text-xs text-slate-900 bg-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-2xs"
              />
            </div>
          </div>

          <div className="pt-2">
            <Button
              type="submit"
              variant="primary"
              size="md"
              isLoading={isLoading}
              rightIcon={<ArrowRight className="w-4 h-4" />}
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold shadow-xs"
            >
              {isLoading ? t.requestServicePage.submittingBtn : t.requestServicePage.submitBtn}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
