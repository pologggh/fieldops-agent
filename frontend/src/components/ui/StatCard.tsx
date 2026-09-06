import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';

export interface StatCardProps {
  title: string;
  value: string | number;
  subtext?: string;
  icon?: React.ReactNode;
  iconBgClass?: string;
  to?: string;
  badge?: React.ReactNode;
  variant?: 'default' | 'urgent' | 'warning' | 'success';
  className?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtext,
  icon,
  iconBgClass = 'bg-slate-100 text-slate-600',
  to,
  badge,
  variant = 'default',
  className = '',
}) => {
  const variantBorder = {
    default: 'border-slate-200 hover:border-slate-300',
    urgent: 'border-rose-200 bg-gradient-to-br from-rose-50/50 to-white hover:border-rose-300',
    warning: 'border-amber-200 bg-gradient-to-br from-amber-50/50 to-white hover:border-amber-300',
    success: 'border-emerald-200 bg-gradient-to-br from-emerald-50/50 to-white hover:border-emerald-300',
  };

  const content = (
    <div
      className={`relative bg-white rounded-xl border p-5 shadow-card transition-all group ${variantBorder[variant]} ${className}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
          {title}
        </span>
        <div className="flex items-center space-x-2">
          {badge}
          {icon && (
            <div
              className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${iconBgClass}`}
            >
              {icon}
            </div>
          )}
        </div>
      </div>

      <div className="mt-3 flex items-baseline justify-between">
        <div className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight font-mono">
          {value}
        </div>
        {to && (
          <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-slate-700 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
        )}
      </div>

      {subtext && <p className="text-xs text-slate-500 mt-1">{subtext}</p>}
    </div>
  );

  if (to) {
    return <Link to={to} className="block focus:outline-none">{content}</Link>;
  }

  return content;
};
