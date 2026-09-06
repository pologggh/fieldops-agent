import React, { useState, useRef, useEffect } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useCustomerAuth } from '../../auth/useCustomerAuth';
import {
  Wrench,
  Calendar,
  ClipboardList,
  PlusCircle,
  User as UserIcon,
  LogOut,
  Sparkles,
  Home,
  Shield,
  ChevronDown,
  ExternalLink,
} from 'lucide-react';

export const CustomerLayout: React.FC = () => {
  const { customer, logout } = useCustomerAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const desktopNavItems = [
    { label: '首页', path: '/customer', icon: Home, exact: true },
    { label: 'AI 智能报修', path: '/customer/assistant', icon: Sparkles, highlight: true },
    { label: '我的工单', path: '/customer/requests', icon: ClipboardList },
    { label: '上门预约', path: '/customer/appointments', icon: Calendar },
  ];

  const mobileBottomNavItems = [
    { label: '首页', path: '/customer', icon: Home, exact: true },
    { label: 'AI 报修', path: '/customer/assistant', icon: Sparkles, highlight: true },
    { label: '工单', path: '/customer/requests', icon: ClipboardList },
    { label: '预约', path: '/customer/appointments', icon: Calendar },
    { label: '我的', path: '/customer/profile', icon: UserIcon },
  ];

  const isActive = (path: string, exact?: boolean) => {
    if (exact) {
      return location.pathname === path;
    }
    return location.pathname.startsWith(path) && (path !== '/customer' || location.pathname === '/customer');
  };

  const handleLogout = () => {
    setUserMenuOpen(false);
    logout();
    navigate('/customer/login');
  };

  const getInitials = (name?: string) => {
    if (!name) return '客';
    const trimmed = name.trim();
    return trimmed.slice(0, 1).toUpperCase();
  };

  return (
    <div className="min-h-screen customer-ambient-bg flex flex-col selection:bg-indigo-500/10 selection:text-indigo-900 pb-16 md:pb-0">
      {/* Top Sticky Frosted Brand Header */}
      <header className="bg-white/85 backdrop-blur-md border-b border-slate-200/80 sticky top-0 z-30 transition-shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Brand Area */}
            <div className="flex items-center space-x-3">
              <Link to="/customer" className="flex items-center space-x-3 group">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-slate-900 via-indigo-950 to-indigo-800 flex items-center justify-center text-white shadow-xs ring-1 ring-slate-900/10 group-hover:scale-[1.02] transition-transform">
                  <Wrench className="w-4 h-4 text-indigo-200" />
                </div>
                <div className="flex items-baseline space-x-2">
                  <span className="text-base font-bold tracking-tight text-slate-900 group-hover:text-indigo-600 transition-colors">
                    FieldOps
                  </span>
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200/60">
                    客户服务中心
                  </span>
                </div>
              </Link>
            </div>

            {/* Desktop Center Navigation (Clean, without Profile/SignOut taking space) */}
            <nav className="hidden md:flex items-center space-x-1">
              {desktopNavItems.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.path, item.exact);
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`relative flex items-center space-x-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                      active
                        ? 'bg-indigo-50 text-indigo-700 font-bold shadow-2xs'
                        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/70'
                    }`}
                  >
                    <Icon className={`w-3.5 h-3.5 ${active ? 'text-indigo-600' : 'text-slate-400'}`} />
                    <span>{item.label}</span>
                    {item.highlight && !active && (
                      <span className="w-1.5 h-1.5 rounded-full bg-violet-500 ml-0.5" />
                    )}
                  </Link>
                );
              })}
            </nav>

            {/* Right User Profile Dropdown & Quick Control */}
            <div className="flex items-center space-x-3" ref={userMenuRef}>
              <Link
                to="/login"
                title="切换至内部运维调度控制台"
                className="hidden lg:inline-flex items-center text-xs font-medium text-slate-500 hover:text-indigo-600 px-2.5 py-1.5 rounded-lg border border-slate-200 hover:border-indigo-200 bg-white/60 hover:bg-white transition-all shadow-2xs"
              >
                <Shield className="w-3.5 h-3.5 mr-1.5 text-slate-400" />
                <span>调度控制台</span>
              </Link>

              {/* User Dropdown Trigger */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center space-x-2 p-1.5 sm:px-2.5 sm:py-1.5 rounded-xl border border-slate-200/80 bg-white/70 hover:bg-white hover:border-slate-300 transition-all shadow-2xs cursor-pointer text-left"
                  aria-expanded={userMenuOpen}
                >
                  <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-bold text-xs shadow-2xs shrink-0">
                    {getInitials(customer?.name)}
                  </div>
                  <div className="hidden sm:block text-left pr-1">
                    <div className="text-xs font-bold text-slate-800 leading-tight">
                      {customer?.name || '张伟 (客户演示)'}
                    </div>
                  </div>
                  <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${userMenuOpen ? 'rotate-180' : ''}`} />
                </button>

                {/* Dropdown Menu */}
                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-52 bg-white rounded-2xl shadow-xl border border-slate-200 py-1.5 z-50 animate-in fade-in zoom-in-95 duration-100">
                    <div className="px-3.5 py-2 border-b border-slate-100 mb-1">
                      <p className="text-[11px] font-semibold text-slate-400">已登录客户</p>
                      <p className="text-xs font-bold text-slate-800 truncate">{customer?.name || '张伟'}</p>
                      <p className="text-[11px] text-slate-500 truncate">{customer?.email || 'alice.test@example.com'}</p>
                    </div>

                    <Link
                      to="/customer/profile"
                      onClick={() => setUserMenuOpen(false)}
                      className="flex items-center px-3.5 py-2 text-xs text-slate-700 hover:bg-slate-50 hover:text-indigo-600 transition-colors"
                    >
                      <UserIcon className="w-3.5 h-3.5 mr-2.5 text-slate-400" />
                      <span>个人资料与常用地址</span>
                    </Link>

                    <Link
                      to="/customer/requests/new"
                      onClick={() => setUserMenuOpen(false)}
                      className="flex items-center px-3.5 py-2 text-xs text-slate-700 hover:bg-slate-50 hover:text-indigo-600 transition-colors"
                    >
                      <PlusCircle className="w-3.5 h-3.5 mr-2.5 text-slate-400" />
                      <span>填写报修单</span>
                    </Link>

                    <div className="border-t border-slate-100 my-1" />

                    <button
                      type="button"
                      onClick={handleLogout}
                      className="w-full flex items-center px-3.5 py-2 text-xs text-rose-600 hover:bg-rose-50 transition-colors"
                    >
                      <LogOut className="w-3.5 h-3.5 mr-2.5 text-rose-500" />
                      <span>退出登录</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Page Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        <Outlet />
      </main>

      {/* Mobile Bottom Navigation Bar (Section 86: 首页, AI 报修, 工单, 预约, 我的) */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t border-slate-200/80 shadow-lg px-2 py-1.5 flex justify-around items-center">
        {mobileBottomNavItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.path, item.exact);
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex flex-col items-center justify-center py-1 px-3 rounded-xl text-[10px] font-medium transition-all ${
                active
                  ? 'text-indigo-600 font-bold'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <div className="relative">
                <Icon className={`w-5 h-5 mb-0.5 ${active ? 'text-indigo-600' : 'text-slate-400'}`} />
                {item.highlight && !active && (
                  <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-violet-500 ring-2 ring-white" />
                )}
              </div>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Subtle Desktop Footer */}
      <footer className="hidden md:block py-6 border-t border-slate-200/60 bg-white/40 mt-auto text-center text-xs text-slate-400">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row justify-between items-center gap-2">
          <span>FieldOps 智能现场运维调度平台 • 客户自助服务中心</span>
          <div className="flex items-center space-x-4 text-[11px] text-slate-500">
            <span>支持热线：400-800-8888</span>
            <span>·</span>
            <span>服务承诺：极速响应 · 准时履约 · 完工质保</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
