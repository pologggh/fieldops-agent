import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useCustomerAuth } from '../../auth/useCustomerAuth';
import * as customerApi from '../../api/customerApi';
import {
  User,
  Phone,
  MapPin,
  Mail,
  CheckCircle2,
  AlertCircle,
  Save,
  ShieldCheck,
  Building,
  KeyRound,
} from 'lucide-react';
import { Button } from '../../components/ui';
import { t } from '../../locales';

export const CustomerProfilePage: React.FC = () => {
  const { customer, refreshProfile } = useCustomerAuth();
  const queryClient = useQueryClient();

  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { data: profile, isLoading } = useQuery({
    queryKey: ['customer-profile'],
    queryFn: customerApi.fetchCustomerProfile,
  });

  useEffect(() => {
    if (profile) {
      setName(profile.name || '');
      setPhone(profile.phone || '');
      setAddress(profile.address || '');
    }
  }, [profile]);

  const updateMutation = useMutation({
    mutationFn: customerApi.updateCustomerProfile,
    onSuccess: async () => {
      await refreshProfile();
      queryClient.invalidateQueries({ queryKey: ['customer-profile'] });
      setSuccessMsg(t.profile.saveSuccess);
      setErrorMsg(null);
      setTimeout(() => setSuccessMsg(null), 4000);
    },
    onError: (err: any) => {
      setErrorMsg(err.message || t.profile.saveError);
      setSuccessMsg(null);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMsg(t.profile.nameRequired);
      return;
    }
    updateMutation.mutate({
      name: name.trim(),
      phone: phone.trim() || undefined,
      address: address.trim() || undefined,
    });
  };

  if (isLoading) {
    return <div className="py-16 text-center text-xs text-slate-400">{t.profile.loading}</div>;
  }

  const userInitial = (name || customer?.name || 'C').charAt(0).toUpperCase();

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-12">
      {/* Header */}
      <div className="pt-1">
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
          {t.profile.title}
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 mt-1">
          {t.profile.subtitle}
        </p>
      </div>

      {/* User Identity Hero Card */}
      <div className="bg-white rounded-3xl border border-slate-200/80 p-6 sm:p-7 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-5">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-600 to-indigo-800 text-white flex items-center justify-center text-2xl font-black shadow-md shadow-indigo-100">
            {userInitial}
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <h2 className="text-lg font-bold text-slate-900">{name || customer?.name}</h2>
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full border border-emerald-200">
                <ShieldCheck className="w-3 h-3 text-emerald-600" />
                认证客户
              </span>
            </div>
            <p className="text-xs text-slate-500 font-mono">{profile?.email || customer?.email}</p>
          </div>
        </div>

        <div className="text-left sm:text-right border-t sm:border-t-0 pt-3 sm:pt-0 border-slate-100">
          <span className="text-[11px] text-slate-400 block font-medium">客户 ID</span>
          <span className="text-sm font-mono font-bold text-slate-700 block">#{customer?.id || profile?.id || 1}</span>
        </div>
      </div>

      {/* Profile Form Card */}
      <div className="bg-white p-6 sm:p-8 rounded-3xl border border-slate-200/80 shadow-xs space-y-6">
        {successMsg && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {errorMsg && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Email (Read Only) */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              {t.profile.accountEmail}
            </label>
            <div className="flex items-center px-3.5 py-2.5 border border-slate-200 rounded-xl bg-slate-50/80 text-slate-500 text-xs cursor-not-allowed">
              <Mail className="w-4 h-4 mr-2.5 text-slate-400 shrink-0" />
              <span className="font-mono">{profile?.email}</span>
            </div>
            <p className="mt-1 text-[11px] text-slate-400">
              {t.profile.emailNotice}
            </p>
          </div>

          {/* Full Name */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              {t.profile.fullName}
            </label>
            <div className="relative">
              <User className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full pl-10 pr-3.5 py-2.5 border border-slate-300 rounded-xl text-xs text-slate-900 bg-white focus:ring-2 focus:ring-indigo-500 focus:outline-none shadow-2xs"
              />
            </div>
          </div>

          {/* Phone */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              {t.profile.phone}
            </label>
            <div className="relative">
              <Phone className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder={t.profile.phonePlaceholder}
                className="w-full pl-10 pr-3.5 py-2.5 border border-slate-300 rounded-xl text-xs text-slate-900 bg-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 focus:outline-none shadow-2xs"
              />
            </div>
          </div>

          {/* Default Address */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              {t.profile.defaultAddress}
            </label>
            <div className="relative">
              <MapPin className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder={t.profile.addressPlaceholder}
                className="w-full pl-10 pr-3.5 py-2.5 border border-slate-300 rounded-xl text-xs text-slate-900 bg-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 focus:outline-none shadow-2xs"
              />
            </div>
            <p className="mt-1 text-[11px] text-slate-400">
              {t.profile.addressNotice}
            </p>
          </div>

          <div className="pt-2">
            <Button
              type="submit"
              variant="primary"
              size="md"
              isLoading={updateMutation.isPending}
              leftIcon={<Save className="w-4 h-4" />}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold"
            >
              {updateMutation.isPending ? t.profile.savingBtn : t.profile.saveBtn}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
