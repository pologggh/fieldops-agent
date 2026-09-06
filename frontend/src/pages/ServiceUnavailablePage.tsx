import React from 'react';
import { ServerCrash, RefreshCw, Home } from 'lucide-react';
import { Button } from '../components/ui/Button';

export const ServiceUnavailablePage: React.FC = () => {
  const handleReload = () => {
    window.location.reload();
  };

  return (
    <div className="min-h-[75vh] flex flex-col items-center justify-center text-center p-6 font-sans">
      <div className="w-16 h-16 rounded-2xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600 mb-5 shadow-xs">
        <ServerCrash className="w-8 h-8" />
      </div>
      <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-amber-50 text-amber-800 border border-amber-200 mb-3">
        状态码 503 · 服务暂时不可用
      </span>
      <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
        现场服务引擎维护中
      </h1>
      <p className="text-xs sm:text-sm text-slate-500 max-w-md mt-2 mb-6 leading-relaxed">
        后端 API 服务或数据库连接暂时不可达，系统自动重连工作进程正在处理中。请稍后重试。
      </p>
      <div className="flex items-center gap-3">
        <Button
          variant="primary"
          size="sm"
          onClick={handleReload}
          leftIcon={<RefreshCw className="w-4 h-4" />}
        >
          重新连接
        </Button>
        <a href="/">
          <Button variant="outline" size="sm" leftIcon={<Home className="w-4 h-4" />}>
            返回平台首页
          </Button>
        </a>
      </div>
    </div>
  );
};
