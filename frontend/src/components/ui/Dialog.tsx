import React, { useEffect, useRef } from 'react';
import { X, AlertTriangle, AlertOctagon, Info } from 'lucide-react';
import { Button } from './Button';

export interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm?: () => void | Promise<void>;
  variant?: 'primary' | 'danger' | 'warning' | 'info';
  isLoading?: boolean;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl';
}

export const Dialog: React.FC<DialogProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  confirmLabel,
  cancelLabel,
  onConfirm,
  variant = 'primary',
  isLoading = false,
  maxWidth = 'md',
}) => {
  const isCustomer = typeof window !== 'undefined' && window.location.pathname.startsWith('/customer');
  const resolvedCancelLabel = cancelLabel ?? (isCustomer ? '取消' : 'Cancel');

  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isLoading) {
        onClose();
      }
    };

    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, isLoading, onClose]);

  if (!isOpen) return null;

  const maxWidthClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
  };

  const variantIcons = {
    primary: <Info className="w-5 h-5 text-indigo-600" />,
    danger: <AlertOctagon className="w-5 h-5 text-rose-600" />,
    warning: <AlertTriangle className="w-5 h-5 text-amber-600" />,
    info: <Info className="w-5 h-5 text-sky-600" />,
  };

  const variantBg = {
    primary: 'bg-indigo-50',
    danger: 'bg-rose-50',
    warning: 'bg-amber-50',
    info: 'bg-sky-50',
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs transition-opacity animate-in fade-in duration-150"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isLoading) {
          onClose();
        }
      }}
    >
      <div
        ref={dialogRef}
        className={`w-full ${maxWidthClasses[maxWidth]} bg-white rounded-2xl shadow-elevated border border-slate-200 overflow-hidden transform transition-all animate-in zoom-in-95 duration-150`}
      >
        <div className="p-5 sm:p-6">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center space-x-3">
              <div
                className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${variantBg[variant]}`}
              >
                {variantIcons[variant]}
              </div>
              <div>
                <h3 id="dialog-title" className="text-base font-bold text-slate-900">
                  {title}
                </h3>
                {description && (
                  <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{description}</p>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              disabled={isLoading}
              aria-label={isCustomer ? "关闭对话框" : "Close dialog"}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {children && <div className="mt-4 text-sm text-slate-600">{children}</div>}

          {(onConfirm || confirmLabel) && (
            <div className="mt-6 flex items-center justify-end space-x-3 pt-3 border-t border-slate-100">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onClose}
                disabled={isLoading}
              >
                {resolvedCancelLabel}
              </Button>
              {confirmLabel && onConfirm && (
                <Button
                  type="button"
                  variant={variant === 'danger' ? 'danger' : 'primary'}
                  size="sm"
                  isLoading={isLoading}
                  onClick={onConfirm}
                >
                  {confirmLabel}
                </Button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
