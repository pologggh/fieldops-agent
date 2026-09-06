import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useCustomerAuth } from '../../auth/useCustomerAuth';
import {
  Wrench,
  ArrowRight,
  AlertCircle,
  Eye,
  EyeOff,
  User,
  CheckCircle2,
  ChevronRight,
} from 'lucide-react';
import { t } from '../../locales';

export const CustomerLoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const { login } = useCustomerAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const handleFillDemo = () => {
    setEmail('alice.test@example.com');
    setPassword('password123');
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('请输入电子邮箱和密码。');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await login({ email, password });
      const returnUrl = searchParams.get('returnUrl') || '/customer';
      navigate(returnUrl, { replace: true });
    } catch (err: any) {
      setError(err.message || '邮箱或密码不正确，请重新输入。');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f] flex flex-col justify-between font-sans antialiased selection:bg-[#1d1d1f] selection:text-white">
      {/* Apple-style Minimal Top Header */}
      <header className="w-full bg-[#f5f5f7]/80 backdrop-blur-md border-b border-[#d2d2d7]/50 sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-6 h-12 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-[15px] tracking-tight text-[#1d1d1f]">
              FieldOps
            </span>
            <span className="text-[#86868b] text-[13px] font-normal">
              客户服务中心
            </span>
          </div>

          <Link
            to="/login"
            className="text-[13px] text-[#0071e3] hover:underline flex items-center gap-0.5 transition-colors"
          >
            <span>企业调度员入口</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </header>

      {/* Main Centered Login Section */}
      <main className="flex-1 flex items-center justify-center px-4 py-12 sm:py-16">
        <div className="w-full max-w-[440px] mx-auto">
          {/* Apple ID Style Icon & Heading */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-[#1d1d1f] text-white mb-4 shadow-xs">
              <Wrench className="w-7 h-7 stroke-[1.75]" />
            </div>
            <h1 className="text-[26px] sm:text-[28px] font-semibold text-[#1d1d1f] tracking-tight">
              {t.auth.loginTitle}
            </h1>
            <p className="mt-2 text-[14px] text-[#86868b]">
              {t.auth.loginSubtitle}
            </p>
          </div>

          {/* Clean Card */}
          <div className="bg-white rounded-2xl p-7 sm:p-9 shadow-[0_4px_24px_rgba(0,0,0,0.04)] border border-[#d2d2d7]/70">
            {searchParams.get('registered') && (
              <div className="mb-6 rounded-xl bg-[#f2faf4] border border-[#bce8c9] p-3.5 text-[#1b7e3a] text-[13px] flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-[#1b7e3a] shrink-0" />
                <span>{t.auth.regSuccessAlert}</span>
              </div>
            )}

            {error && (
              <div className="mb-6 rounded-xl bg-[#fff2f2] border border-[#ffc8c8] p-3.5 flex items-start gap-2.5 text-[13px] text-[#d70015]">
                <AlertCircle className="w-4 h-4 text-[#d70015] shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form className="space-y-4" onSubmit={handleSubmit}>
              <div>
                <label className="block text-[12px] font-medium text-[#6e6e73] mb-1.5">
                  {t.auth.emailLabel}
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={t.auth.emailPlaceholder}
                  className="w-full h-12 px-3.5 bg-white border border-[#d2d2d7] rounded-xl text-[14px] text-[#1d1d1f] placeholder-[#86868b] focus:outline-none focus:border-[#0071e3] focus:ring-4 focus:ring-[#0071e3]/15 transition-all"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-[12px] font-medium text-[#6e6e73]">
                    {t.auth.passwordLabel}
                  </label>
                </div>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={t.auth.passwordPlaceholder}
                    className="w-full h-12 pl-3.5 pr-11 bg-white border border-[#d2d2d7] rounded-xl text-[14px] text-[#1d1d1f] placeholder-[#86868b] focus:outline-none focus:border-[#0071e3] focus:ring-4 focus:ring-[#0071e3]/15 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-[#86868b] hover:text-[#1d1d1f] cursor-pointer"
                    title={showPassword ? '隐藏密码' : '显示密码'}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full h-11 mt-2 flex justify-center items-center rounded-xl bg-[#0071e3] hover:bg-[#0077ed] text-white text-[14px] font-medium tracking-tight shadow-none transition-all disabled:opacity-50 cursor-pointer"
              >
                {isLoading ? t.auth.signingInBtn : t.auth.signInBtn}
                <ArrowRight className="ml-1.5 w-4 h-4" />
              </button>
            </form>

            {/* Apple-style 1-Click Demo Account Card */}
            <div className="mt-6 pt-5 border-t border-[#e5e5ea]">
              <button
                type="button"
                onClick={handleFillDemo}
                className="w-full py-2.5 px-3 bg-[#f5f5f7] hover:bg-[#e8e8ed] border border-[#d2d2d7]/70 rounded-xl text-[13px] font-medium text-[#1d1d1f] transition-all flex items-center justify-between cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-[#1d1d1f] text-white flex items-center justify-center text-[11px] font-semibold">
                    张
                  </div>
                  <span className="text-[12px] text-[#424245]">
                    {t.auth.fillDemoCustomer}
                  </span>
                </div>
                <span className="text-[11px] text-[#0071e3] font-normal">
                  填入 ›
                </span>
              </button>
            </div>

            <div className="mt-6 text-center text-[13px] text-[#6e6e73]">
              {t.auth.noAccountText}{' '}
              <Link
                to="/customer/register"
                className="text-[#0071e3] hover:underline font-medium"
              >
                {t.auth.createAccountLink}
              </Link>
            </div>

            <div className="mt-4 pt-4 border-t border-[#e5e5ea] text-center text-[12px] text-[#86868b]">
              {t.auth.operatorPrompt}{' '}
              <Link
                to="/login"
                className="text-[#0071e3] hover:underline"
              >
                调度控制台与管理中心入口 ›
              </Link>
            </div>
          </div>
        </div>
      </main>

      {/* Apple-style Footer */}
      <footer className="w-full max-w-5xl mx-auto px-6 py-6 border-t border-[#d2d2d7]/50 text-center text-[12px] text-[#86868b] space-y-2">
        <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-1">
          <span>FieldOps 客户自助服务</span>
          <span>·</span>
          <span>服务时效承诺</span>
          <span>·</span>
          <span>用户隐私政策</span>
          <span>·</span>
          <Link to="/login" className="text-[#0071e3] hover:underline">
            调度工作台
          </Link>
        </div>
        <p className="text-[11px] text-[#86868b]/80">
          Copyright © 2026 FieldOps Inc. 保留所有权利。全天候 7×24 小时服务支持。
        </p>
      </footer>
    </div>
  );
};
