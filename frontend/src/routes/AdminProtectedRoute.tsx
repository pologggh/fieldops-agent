import React from 'react';
import { Navigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

interface AdminProtectedRouteProps {
  children: React.ReactNode;
}

export const AdminProtectedRoute: React.FC<AdminProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-slate-600 font-medium text-sm">正在验证系统管理员权限...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (user?.role !== 'admin') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
        <div className="max-w-md w-full bg-white rounded-xl shadow-lg p-8 border border-rose-100 text-center">
          <div className="w-16 h-16 bg-rose-100 text-rose-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl font-bold">
            !
          </div>
          <h2 className="text-2xl font-bold text-slate-900 mb-2">403 - 无访问权限</h2>
          <p className="text-slate-600 text-sm mb-6">
            系统治理控制台仅限系统管理员（admin）访问。您当前账号角色为：{' '}
            <span className="inline-block px-2 py-0.5 bg-slate-100 text-slate-800 rounded font-semibold">
              {user?.role === 'operator' ? '调度员' : user?.role === 'viewer' ? '只读观察员' : user?.role || '未分配'}
            </span>。
          </p>
          <div className="flex flex-col gap-3">
            <Link
              to="/"
              className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg shadow-sm transition-colors text-center text-sm"
            >
              返回调度控制台
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};
