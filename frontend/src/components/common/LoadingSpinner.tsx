import React from 'react';

interface LoadingSpinnerProps {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  label = '正在加载中...',
  size = 'md',
  className = '',
}) => {
  const sizeClasses = {
    sm: 'w-4 h-4 border-2',
    md: 'w-8 h-8 border-3',
    lg: 'w-12 h-12 border-4',
  };

  return (
    <div
      role="status"
      aria-label={label}
      className={`flex flex-col items-center justify-center p-6 text-slate-500 ${className}`}
    >
      <div
        className={`${sizeClasses[size]} border-slate-200 border-t-indigo-600 rounded-full animate-spin`}
      />
      {label && <span className="mt-2 text-xs font-medium text-slate-500">{label}</span>}
    </div>
  );
};
