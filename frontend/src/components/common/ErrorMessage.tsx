import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorMessageProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({
  title = 'An error occurred',
  message,
  onRetry,
  className = '',
}) => {
  return (
    <div
      role="alert"
      className={`rounded-lg border border-rose-200 bg-rose-50 p-4 text-rose-900 ${className}`}
    >
      <div className="flex items-start">
        <AlertTriangle className="h-5 w-5 text-rose-600 mt-0.5 mr-3 flex-shrink-0" />
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-rose-800">{title}</h3>
          <p className="mt-1 text-sm text-rose-700 leading-relaxed">{message}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 inline-flex items-center px-3 py-1.5 border border-rose-300 shadow-sm text-xs font-medium rounded-md text-rose-800 bg-white hover:bg-rose-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-rose-500"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              Retry Request
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
