import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';
import {
  Lock,
  Mail,
  AlertCircle,
  ArrowRight,
  Loader2,
  Eye,
  EyeOff,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated, user, role } = useAuth();

  const [username, setUsername] = useState('operator@fieldops.com');
  const [password, setPassword] = useState('password123');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selected role preset: 'operator' | 'admin' | 'viewer'
  const [selectedRolePreset, setSelectedRolePreset] = useState<'operator' | 'admin' | 'viewer'>('operator');

  // Preserve both pathname and search parameters from the intended route
  const fromLocation = (location.state as any)?.from;
  const fromPath = fromLocation
    ? `${fromLocation.pathname || '/'}${fromLocation.search || ''}`
    : '/';
  const target = fromPath === '/login' ? '/' : fromPath;

  const getDestination = (userRole?: string | null, intendedTarget: string = target) => {
    if (userRole === 'admin') {
      if (intendedTarget === '/' || intendedTarget === '/login') {
        return '/admin';
      }
      return intendedTarget;
    }
    if (intendedTarget.startsWith('/admin')) {
      return '/';
    }
    return intendedTarget;
  };

  // Auto-redirect if session is already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      const dest = getDestination(role || user?.role, target);
      navigate(dest, { replace: true });
    }
  }, [isAuthenticated, role, user?.role, target, navigate]);

  const performLogin = async (userToLogin: string, passToLogin: string, explicitTarget?: string) => {
    setError(null);
    setIsLoading(true);
    try {
      await login(userToLogin, passToLogin);
      const isUserAdmin = userToLogin.toLowerCase().includes('admin');
      const resolvedTarget = explicitTarget || (isUserAdmin ? '/admin' : getDestination(isUserAdmin ? 'admin' : 'operator'));
      navigate(resolvedTarget, { replace: true });
    } catch (err: any) {
      setError(err.message || '登录认证失败，请核对账号与密码是否正确。');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await performLogin(username, password);
  };

  const handleSelectRolePreset = (roleKey: 'operator' | 'admin' | 'viewer') => {
    setSelectedRolePreset(roleKey);
    let email = 'operator@fieldops.com';
    if (roleKey === 'admin') email = 'admin@fieldops.com';
    if (roleKey === 'viewer') email = 'viewer@fieldops.com';
    setUsername(email);
    setPassword('password123');
  };

  const getRoleDescription = () => {
    switch (selectedRolePreset) {
      case 'operator':
        return '调度员身份 · 负责服务工单调度大厅、预约确认与工程师派单';
      case 'admin':
        return '系统管理员 · 负责服务网点、班组名册、派单策略与系统设置';
      case 'viewer':
        return '只读观察员 · 负责调度总览大屏数据观测与合规审计查阅';
      default:
        return '';
    }
  };

  return (
    <div className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f] flex flex-col justify-between font-sans antialiased selection:bg-[#1d1d1f] selection:text-white">
      {/* Apple-style Minimal Top Navigation Bar */}
      <header className="w-full bg-[#f5f5f7]/80 backdrop-blur-md border-b border-[#d2d2d7]/50 sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-6 h-12 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-[15px] tracking-tight text-[#1d1d1f]">
              FieldOps
            </span>
            <span className="text-[#86868b] text-[13px] font-normal">
              工作台
            </span>
          </div>

          <Link
            to="/customer"
            className="text-[13px] text-[#0071e3] hover:underline flex items-center gap-0.5 transition-colors"
          >
            <span>前往客户报修门户</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </header>

      {/* Main Centered Sign-in Section */}
      <main className="flex-1 flex items-center justify-center px-4 py-12 sm:py-16">
        <div className="w-full max-w-[440px] mx-auto">
          {/* Brand Icon & Heading (Apple ID Style) */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-[#1d1d1f] text-white mb-4 shadow-xs">
              <ShieldCheck className="w-7 h-7 stroke-[1.75]" />
            </div>
            <h1 className="text-[26px] sm:text-[28px] font-semibold text-[#1d1d1f] tracking-tight">
              登录 FieldOps 账户
            </h1>
            <p className="mt-2 text-[14px] text-[#86868b]">
              调度指挥大厅与企业控制中心
            </p>
          </div>

          {/* Clean Apple-style Card */}
          <div className="bg-white rounded-2xl p-7 sm:p-9 shadow-[0_4px_24px_rgba(0,0,0,0.04)] border border-[#d2d2d7]/70">
            {/* Error Message */}
            {error && (
              <div className="mb-6 rounded-xl bg-[#fff2f2] border border-[#ffc8c8] p-3.5 flex items-start gap-2.5 text-[13px] text-[#d70015]">
                <AlertCircle className="w-4 h-4 text-[#d70015] shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {/* Apple-style Segmented Role Selector */}
            <div className="mb-6">
              <div className="text-[12px] font-medium text-[#86868b] mb-2 text-center">
                选择身份快速填入：
              </div>
              <div className="bg-[#f5f5f7] p-1 rounded-xl flex items-center gap-1 border border-[#e5e5ea]">
                <button
                  type="button"
                  onClick={() => handleSelectRolePreset('operator')}
                  className={`flex-1 py-1.5 px-2 text-xs font-medium rounded-lg transition-all cursor-pointer text-center ${
                    selectedRolePreset === 'operator'
                      ? 'bg-white text-[#1d1d1f] shadow-xs font-semibold'
                      : 'text-[#6e6e73] hover:text-[#1d1d1f]'
                  }`}
                >
                  调度员
                </button>
                <button
                  type="button"
                  onClick={() => handleSelectRolePreset('admin')}
                  className={`flex-1 py-1.5 px-2 text-xs font-medium rounded-lg transition-all cursor-pointer text-center ${
                    selectedRolePreset === 'admin'
                      ? 'bg-white text-[#1d1d1f] shadow-xs font-semibold'
                      : 'text-[#6e6e73] hover:text-[#1d1d1f]'
                  }`}
                >
                  管理员
                </button>
                <button
                  type="button"
                  onClick={() => handleSelectRolePreset('viewer')}
                  className={`flex-1 py-1.5 px-2 text-xs font-medium rounded-lg transition-all cursor-pointer text-center ${
                    selectedRolePreset === 'viewer'
                      ? 'bg-white text-[#1d1d1f] shadow-xs font-semibold'
                      : 'text-[#6e6e73] hover:text-[#1d1d1f]'
                  }`}
                >
                  观察员
                </button>
              </div>
              <p className="text-[11px] text-[#86868b] mt-2 text-center leading-normal">
                {getRoleDescription()}
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Username Input */}
              <div>
                <label className="block text-[12px] font-medium text-[#6e6e73] mb-1.5">
                  企业邮箱或工号
                </label>
                <div className="relative">
                  <input
                    type="text"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full h-12 px-3.5 bg-white border border-[#d2d2d7] rounded-xl text-[14px] text-[#1d1d1f] placeholder-[#86868b] focus:outline-none focus:border-[#0071e3] focus:ring-4 focus:ring-[#0071e3]/15 transition-all"
                    placeholder="name@fieldops.com"
                    disabled={isLoading}
                  />
                </div>
              </div>

              {/* Password Input */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-[12px] font-medium text-[#6e6e73]">
                    密码
                  </label>
                  <span className="text-[11px] text-[#86868b]">
                    默认密码：password123
                  </span>
                </div>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full h-12 pl-3.5 pr-11 bg-white border border-[#d2d2d7] rounded-xl text-[14px] text-[#1d1d1f] placeholder-[#86868b] focus:outline-none focus:border-[#0071e3] focus:ring-4 focus:ring-[#0071e3]/15 transition-all"
                    placeholder="••••••••"
                    disabled={isLoading}
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

              {/* Stay signed in */}
              <div className="flex items-center justify-between pt-1">
                <label className="flex items-center text-[13px] text-[#424245] cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="w-4 h-4 text-[#0071e3] rounded border-[#d2d2d7] focus:ring-[#0071e3] cursor-pointer"
                  />
                  <span className="ml-2">保持登录状态</span>
                </label>
              </div>

              {/* Sign In Button (Apple Primary Button Style) */}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full h-11 mt-2 flex justify-center items-center rounded-xl bg-[#0071e3] hover:bg-[#0077ed] text-white text-[14px] font-medium tracking-tight shadow-none transition-all disabled:opacity-50 cursor-pointer"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    正在登录...
                  </>
                ) : (
                  <>
                    登录
                    <ArrowRight className="w-4 h-4 ml-1.5" />
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      </main>

      {/* Apple-style Clean Legal & Telemetry Footer */}
      <footer className="w-full max-w-5xl mx-auto px-6 py-6 border-t border-[#d2d2d7]/50 text-center text-[12px] text-[#86868b] space-y-2">
        <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-1">
          <span>FieldOps 统一身份凭据</span>
          <span>·</span>
          <span>隐私与安全保护</span>
          <span>·</span>
          <span>使用规范</span>
          <span>·</span>
          <Link to="/customer" className="text-[#0071e3] hover:underline">
            客户服务中心
          </Link>
        </div>
        <p className="text-[11px] text-[#86868b]/80">
          Copyright © 2026 FieldOps Inc. 保留所有权利。中国标准时间 (UTC+8) 运行。
        </p>
      </footer>
    </div>
  );
};
