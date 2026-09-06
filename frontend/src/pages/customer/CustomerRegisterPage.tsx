import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useCustomerAuth } from '../../auth/useCustomerAuth';
import {
  Wrench,
  ArrowRight,
  AlertCircle,
  Eye,
  EyeOff,
  ChevronRight,
} from 'lucide-react';
import { t } from '../../locales';

export const CustomerRegisterPage: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const { register } = useCustomerAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email || !password) {
      setError('请完整填写所有必填字段。');
      return;
    }
    if (password.length < 6) {
      setError('密码长度至少需要 6 个字符。');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await register({ name, email, password, phone });
      navigate('/customer', { replace: true });
    } catch (err: any) {
      setError(err.message || '注册失败，该邮箱地址可能已被注册。');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f] flex flex-col justify-between font-sans antialiased selection:bg-[#1d1d1f] selection:text-white">
      {/* Top Header */}
      <header className="w-full bg-[#f5f5f7]/80 backdrop-blur-md border-b border-[#d2d2d7]/50 sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-6 h-12 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-[15px] tracking-tight text-[#1d1d1f]">
              FieldOps
            </span>
            <span className="text-[#86868b] text-[13px] font-normal">
              客户账号服务
            </span>
          </div>

          <Link
            to="/customer/login"
            className="text-[13px] text-[#0071e3] hover:underline flex items-center gap-0.5 transition-colors"
          >
            <span>已有账户登录</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </header>

      {/* Centered Register Form Section */}
      <main className="flex-1 flex items-center justify-center px-4 py-12 sm:py-16">
        <div className="w-full max-w-[440px] mx-auto">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-[#1d1d1f] text-white mb-4 shadow-xs">
              <Wrench className="w-7 h-7 stroke-[1.75]" />
            </div>
            <h1 className="text-[26px] sm:text-[28px] font-semibold text-[#1d1d1f] tracking-tight">
              {t.auth.registerTitle}
            </h1>
            <p className="mt-2 text-[14px] text-[#86868b]">
              {t.auth.registerSubtitle}
            </p>
          </div>

          <div className="bg-white rounded-2xl p-7 sm:p-9 shadow-[0_4px_24px_rgba(0,0,0,0.04)] border border-[#d2d2d7]/70">
            {error && (
              <div className="mb-6 rounded-xl bg-[#fff2f2] border border-[#ffc8c8] p-3.5 flex items-start gap-2.5 text-[13px] text-[#d70015]">
                <AlertCircle className="w-4 h-4 text-[#d70015] shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form className="space-y-4" onSubmit={handleSubmit}>
              <div>
                <label className="block text-[12px] font-medium text-[#6e6e73] mb-1.5">
                  {t.auth.fullNameLabel} *
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t.auth.fullNamePlaceholder}
                  className="w-full h-12 px-3.5 bg-white border border-[#d2d2d7] rounded-xl text-[14px] text-[#1d1d1f] placeholder-[#86868b] focus:outline-none focus:border-[#0071e3] focus:ring-4 focus:ring-[#0071e3]/15 transition-all"
                />
              </div>

              <div>
                <label className="block text-[12px] font-medium text-[#6e6e73] mb-1.5">
                  {t.auth.emailLabel} *
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
                <label className="block text-[12px] font-medium text-[#6e6e73] mb-1.5">
                  {t.auth.phoneLabel}
                </label>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="13800138000"
                  className="w-full h-12 px-3.5 bg-white border border-[#d2d2d7] rounded-xl text-[14px] text-[#1d1d1f] placeholder-[#86868b] focus:outline-none focus:border-[#0071e3] focus:ring-4 focus:ring-[#0071e3]/15 transition-all"
                />
              </div>

              <div>
                <label className="block text-[12px] font-medium text-[#6e6e73] mb-1.5">
                  {t.auth.createPasswordLabel} *
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={t.auth.passwordHint}
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
                {isLoading ? t.auth.registeringBtn : t.auth.registerBtn}
                <ArrowRight className="ml-1.5 w-4 h-4" />
              </button>
            </form>

            <div className="mt-6 text-center text-[13px] text-[#6e6e73]">
              {t.auth.hasAccountText}{' '}
              <Link
                to="/customer/login"
                className="text-[#0071e3] hover:underline font-medium"
              >
                {t.auth.toSignInLink}
              </Link>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full max-w-5xl mx-auto px-6 py-6 border-t border-[#d2d2d7]/50 text-center text-[12px] text-[#86868b]">
        <p className="text-[11px] text-[#86868b]/80">
          Copyright © 2026 FieldOps Inc. 保留所有权利。
        </p>
      </footer>
    </div>
  );
};
