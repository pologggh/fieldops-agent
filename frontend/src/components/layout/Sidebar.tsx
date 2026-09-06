import React from 'react';
import { NavLink, Link } from 'react-router-dom';
import {
  LayoutDashboard,
  ClipboardList,
  CalendarCheck2,
  AlertOctagon,
  Activity,
  Shield,
  ShieldAlert,
  Wrench,
  ExternalLink,
} from 'lucide-react';
import { useAuth } from '../../auth/useAuth';

export const Sidebar: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const navItems = [
    {
      name: '工作台',
      path: '/',
      icon: LayoutDashboard,
    },
    {
      name: '服务工单',
      path: '/service-requests',
      icon: ClipboardList,
    },
    {
      name: '上门预约',
      path: '/appointments',
      icon: CalendarCheck2,
    },
    {
      name: '升级处理',
      path: '/escalations',
      icon: AlertOctagon,
    },
    {
      name: '系统状态',
      path: '/system',
      icon: Activity,
    },
  ];

  return (
    <aside className="w-64 bg-slate-900 text-slate-200 flex flex-col flex-shrink-0 border-r border-slate-800">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 border-b border-slate-800 bg-slate-950/40">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold shadow-md shadow-indigo-600/30">
            <Shield className="w-4 h-4" />
          </div>
          <div>
            <span className="font-bold text-base text-white tracking-tight">FieldOps</span>
            <span className="block text-[10px] text-indigo-300 font-medium tracking-wide">
              智能调度中心
            </span>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
          调度业务
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                }`
              }
            >
              <Icon className="w-4 h-4 mr-3 flex-shrink-0" />
              <span>{item.name}</span>
            </NavLink>
          );
        })}

        {/* Admin Console Entry (Visible for Admin Users) */}
        {isAdmin && (
          <>
            <div className="pt-4 pb-2 px-3 text-[10px] font-bold uppercase tracking-wider text-slate-500">
              系统治理
            </div>
            <Link
              to="/admin"
              className="flex items-center px-3 py-2.5 rounded-lg text-sm font-medium text-rose-300 hover:bg-rose-950/40 border border-rose-900/40 transition-colors group"
            >
              <ShieldAlert className="w-4 h-4 mr-3 text-rose-400" />
              <span>管理控制台</span>
              <ExternalLink className="w-3.5 h-3.5 ml-auto opacity-70 group-hover:opacity-100" />
            </Link>
          </>
        )}

        <div className="pt-4 pb-2 px-3 text-[10px] font-bold uppercase tracking-wider text-slate-500">
          门户切换
        </div>
        <Link
          to="/customer"
          className="flex items-center px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-emerald-400 hover:bg-slate-800/60 transition-colors"
        >
          <Wrench className="w-4 h-4 mr-3 text-emerald-500" />
          <span>客户自助服务中心</span>
          <ExternalLink className="w-3 h-3 ml-auto opacity-70" />
        </Link>
      </nav>

      {/* User Info Bar at Bottom */}
      {user && (
        <div className="p-4 border-t border-slate-800 bg-slate-950/40">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center font-bold text-slate-300 text-xs">
              {user.name.slice(0, 1)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-slate-200 truncate">{user.name}</div>
              <div className="text-[10px] text-slate-500 truncate">{user.email}</div>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};
