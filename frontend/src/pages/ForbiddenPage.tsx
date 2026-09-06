import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldX, Home, UserCheck } from 'lucide-react';
import { Button } from '../components/ui/Button';

export const ForbiddenPage: React.FC = () => {
  return (
    <div className="min-h-[75vh] flex flex-col items-center justify-center text-center p-6 font-sans">
      <div className="w-16 h-16 rounded-2xl bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600 mb-5 shadow-xs">
        <ShieldX className="w-8 h-8" />
      </div>
      <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-rose-50 text-rose-700 border border-rose-200 mb-3">
        状态码 403 · 无访问权限
      </span>
      <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
        您没有权限执行此操作
      </h1>
      <p className="text-xs sm:text-sm text-slate-500 max-w-md mt-2 mb-6 leading-relaxed">
        您当前账号的角色权限不足以访问该管理视图或执行该调度操作。如需开通权限，请联系企业系统管理员。
      </p>
      <div className="flex items-center gap-3">
        <Link to="/">
          <Button variant="primary" size="sm" leftIcon={<Home className="w-4 h-4" />}>
            返回调度工作台
          </Button>
        </Link>
        <Link to="/login">
          <Button variant="outline" size="sm" leftIcon={<UserCheck className="w-4 h-4" />}>
            切换账号登录
          </Button>
        </Link>
      </div>
    </div>
  );
};
