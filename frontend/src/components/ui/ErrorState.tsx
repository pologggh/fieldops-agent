import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from './Button';

export interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  requestId?: string | number;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title,
  message,
  onRetry,
  requestId,
  className = '',
}) => {
  const resolvedTitle = title ?? '系统处理异常';

  return (
    <div
      role="alert"
      className={`rounded-xl border border-rose-200 bg-rose-50/60 p-5 text-rose-900 shadow-xs ${className}`}
    >
      <div className="flex items-start gap-3.5">
        <div className="w-9 h-9 rounded-lg bg-rose-100 flex items-center justify-center shrink-0 text-rose-600">
          <AlertTriangle className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-bold text-rose-900">{resolvedTitle}</h3>
          <p className="mt-1 text-xs text-rose-700 leading-relaxed">{message}</p>
          {requestId && (
            <p className="text-[11px] font-mono text-rose-500 mt-1">追踪编号：#{requestId}</p>
          )}
          {onRetry && (
            <div className="mt-3">
              <Button
                variant="outline"
                size="sm"
                onClick={onRetry}
                leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
                className="border-rose-300 text-rose-800 hover:bg-rose-100/50"
              >
                重试
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
