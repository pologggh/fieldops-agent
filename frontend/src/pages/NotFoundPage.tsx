import React from 'react';
import { Link } from 'react-router-dom';
import { FileQuestion, Home, ArrowLeft } from 'lucide-react';
import { Button } from '../components/ui/Button';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-[75vh] flex flex-col items-center justify-center text-center p-6 font-sans">
      <div className="w-16 h-16 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 mb-5 shadow-xs">
        <FileQuestion className="w-8 h-8" />
      </div>
      <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-slate-100 text-slate-600 border border-slate-200 mb-3">
        状态码 404 · 页面未找到
      </span>
      <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
        未找到相关记录或页面
      </h1>
      <p className="text-xs sm:text-sm text-slate-500 max-w-md mt-2 mb-6 leading-relaxed">
        您访问的工单、页面或资源不存在，可能已被归档或链接地址有误。请返回主页或检查链接。
      </p>
      <div className="flex items-center gap-3">
        <Link to="/">
          <Button variant="primary" size="sm" leftIcon={<Home className="w-4 h-4" />}>
            返回调度工作台
          </Button>
        </Link>
        <Link to="/customer">
          <Button variant="outline" size="sm">
            客户服务中心
          </Button>
        </Link>
      </div>
    </div>
  );
};
