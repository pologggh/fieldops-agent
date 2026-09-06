import React from 'react';
import { useAuth } from '../../auth/useAuth';
import { StatusBadge } from '../common/StatusBadge';
import { LogOut, Clock, Shield } from 'lucide-react';
import { CommandPalette } from '../ui/CommandPalette';

export const Topbar: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between z-10">
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2 text-xs text-slate-500">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <span>时区：<strong className="text-slate-700 font-sans font-semibold">中国标准时间 (UTC+8)</strong></span>
        </div>
        <div className="h-4 w-px bg-slate-200 hidden sm:block" />
        <CommandPalette role={user?.role || 'operator'} />
      </div>

      <div className="flex items-center space-x-4">
        {user && (
          <div className="flex items-center space-x-3">
            <div className="text-right hidden sm:block">
              <div className="text-sm font-semibold text-slate-900 leading-tight">
                {user.name}
              </div>
              <div className="text-xs text-slate-400">{user.email}</div>
            </div>

            <StatusBadge type="role" value={user.role} />

            <div className="h-5 w-px bg-slate-200 mx-1" />

            <button
              onClick={logout}
              title="退出登录"
              aria-label="退出登录"
              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-slate-100 transition-colors flex items-center gap-1 text-xs font-medium"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden md:inline">退出</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
