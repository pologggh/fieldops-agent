import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

export interface PageHeaderProps {
  title: string;
  description?: string;
  backTo?: string;
  backLabel?: string;
  badge?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  backTo,
  backLabel = 'Back',
  badge,
  children,
  className = '',
}) => {
  return (
    <div className={`space-y-2 mb-6 ${className}`}>
      {backTo && (
        <Link
          to={backTo}
          className="inline-flex items-center text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors mb-1 group"
        >
          <ArrowLeft className="w-3.5 h-3.5 mr-1 group-hover:-translate-x-0.5 transition-transform" />
          {backLabel}
        </Link>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{title}</h1>
            {badge}
          </div>
          {description && <p className="text-xs sm:text-sm text-slate-500 mt-1">{description}</p>}
        </div>

        {children && <div className="flex items-center flex-wrap gap-2.5">{children}</div>}
      </div>
    </div>
  );
};
