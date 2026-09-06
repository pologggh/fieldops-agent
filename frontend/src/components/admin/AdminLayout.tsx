import React from 'react';
import { NavLink, Outlet, Link, useNavigate } from 'react-router-dom';
import {
  ShieldAlert,
  Users,
  Wrench,
  Sliders,
  Timer,
  Network,
  FileText,
  Server,
  LogOut,
  LayoutDashboard,
  ExternalLink,
  Building,
  Layers,
} from 'lucide-react';
import { useAuth } from '../../auth/useAuth';
import { CommandPalette } from '../ui/CommandPalette';

export const AdminLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const navItems = [
    { name: '管理概览', path: '/admin', icon: ShieldAlert, end: true },
    { name: '用户管理', path: '/admin/users', icon: Users },
    { name: '服务网点', path: '/admin/branches', icon: Building },
    { name: '服务班组', path: '/admin/teams', icon: Layers },
    { name: '服务工程师', path: '/admin/technicians', icon: Wrench },
    { name: '派单策略', path: '/admin/policies/dispatch', icon: Sliders },
    { name: '服务时效策略', path: '/admin/policies/sla', icon: Timer },
    { name: '集成管理', path: '/admin/integrations', icon: Network },
    { name: '审计日志', path: '/admin/audit', icon: FileText },
    { name: '系统状态', path: '/admin/system', icon: Server },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-slate-100 overflow-hidden font-sans">
      {/* Admin Sidebar */}
      <aside className="w-64 bg-slate-900 text-slate-200 flex flex-col flex-shrink-0 border-r border-slate-800">
        {/* Admin Brand Header */}
        <div className="h-16 flex items-center px-6 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-rose-600 flex items-center justify-center text-white font-bold shadow-md shadow-rose-600/30">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <span className="font-bold text-base text-white tracking-tight">FieldOps</span>
              <span className="block text-[10px] text-rose-400 font-semibold tracking-wide">
                系统治理中心
              </span>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
            治理与配置
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.end}
                className={({ isActive }) =>
                  `flex items-center px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                    isActive
                      ? 'bg-rose-600/20 text-rose-300 border border-rose-500/30'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                  }`
                }
              >
                <Icon className="w-4 h-4 mr-3 shrink-0" />
                <span>{item.name}</span>
              </NavLink>
            );
          })}

          <div className="pt-4 pb-2 px-3 text-[10px] font-bold uppercase tracking-wider text-slate-500">
            控制台切换
          </div>
          <Link
            to="/"
            className="flex items-center px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-indigo-400 hover:bg-slate-800/60 transition-colors"
          >
            <LayoutDashboard className="w-4 h-4 mr-3 text-slate-500 shrink-0" />
            <span>调度员工作台</span>
            <ExternalLink className="w-3 h-3 ml-auto opacity-70" />
          </Link>
          <Link
            to="/customer"
            className="flex items-center px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-emerald-400 hover:bg-slate-800/60 transition-colors mt-1"
          >
            <Wrench className="w-4 h-4 mr-3 text-emerald-500 shrink-0" />
            <span>客户自助服务中心</span>
            <ExternalLink className="w-3 h-3 ml-auto opacity-70" />
          </Link>
        </nav>

        {/* User Info & Sign Out */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/40">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2.5 min-w-0">
              <div className="w-7 h-7 rounded-full bg-rose-950 text-rose-300 border border-rose-800 flex items-center justify-center font-bold text-xs shrink-0">
                {user?.name ? user.name.slice(0, 1) : '管'}
              </div>
              <div className="min-w-0">
                <div className="text-xs font-medium text-slate-200 truncate">{user?.name || '管理员'}</div>
                <div className="text-[10px] text-slate-500 truncate">{user?.email || 'admin@fieldops.com'}</div>
              </div>
            </div>
            <button
              onClick={handleLogout}
              title="退出登录"
              aria-label="退出登录"
              className="p-1.5 text-slate-400 hover:text-rose-400 rounded-lg hover:bg-slate-800/60 transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Admin Content View */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header Bar */}
        <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between flex-shrink-0 z-10 shadow-2xs">
          <div className="flex items-center space-x-3">
            <span className="text-xs font-semibold text-rose-700 bg-rose-50 px-2.5 py-1 rounded-md border border-rose-200">
              系统管理模式
            </span>
            <span className="text-xs text-slate-400">
              所有策略与用户权限操作均将记入不可篡改的审计流
            </span>
          </div>

          <div className="flex items-center space-x-4">
            <CommandPalette role="admin" />
          </div>
        </header>

        {/* Dynamic Admin Route Outlet */}
        <main className="flex-1 overflow-y-auto p-8 bg-slate-50">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
