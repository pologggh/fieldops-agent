import React from 'react';
import { TableSkeleton } from './Skeleton';
import { EmptyState } from '../common/EmptyState';

export interface Column<T> {
  header: string;
  accessor?: keyof T | ((row: T) => React.ReactNode);
  className?: string;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  data?: T[];
  isLoading?: boolean;
  onRowClick?: (row: T) => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: React.ReactNode;
  rowKey?: keyof T | ((row: T) => string | number);
  className?: string;
}

export function DataTable<T>({
  columns,
  data = [],
  isLoading = false,
  onRowClick,
  emptyTitle,
  emptyDescription,
  emptyAction,
  rowKey,
  className = '',
}: DataTableProps<T>) {
  const resolvedEmptyTitle = emptyTitle ?? '暂无相关记录';
  const resolvedEmptyDesc = emptyDescription ?? '没有符合当前筛选条件的数据项。';

  if (isLoading) {
    return <TableSkeleton rows={5} />;
  }

  if (!data || data.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 shadow-card p-8">
        <EmptyState
          title={resolvedEmptyTitle}
          description={resolvedEmptyDesc}
          action={emptyAction}
        />
      </div>
    );
  }

  const getKey = (row: T, index: number): string | number => {
    if (typeof rowKey === 'function') return rowKey(row);
    if (rowKey && row[rowKey] !== undefined) return String(row[rowKey]);
    return index;
  };

  return (
    <div className={`bg-white rounded-xl border border-slate-200 shadow-card overflow-hidden ${className}`}>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left">
          <thead className="bg-slate-50/80 sticky top-0 z-10 backdrop-blur-xs">
            <tr>
              {columns.map((col, idx) => (
                <th
                  key={idx}
                  scope="col"
                  className={`px-5 py-3.5 text-xs font-semibold text-slate-500 uppercase tracking-wider ${col.className || ''}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {data.map((row, rowIdx) => (
              <tr
                key={getKey(row, rowIdx)}
                onClick={() => onRowClick && onRowClick(row)}
                className={`transition-colors ${
                  onRowClick ? 'cursor-pointer hover:bg-slate-50/80' : 'hover:bg-slate-50/40'
                }`}
              >
                {columns.map((col, colIdx) => (
                  <td
                    key={colIdx}
                    className={`px-5 py-3.5 text-xs text-slate-700 whitespace-nowrap ${col.className || ''}`}
                  >
                    {typeof col.accessor === 'function'
                      ? col.accessor(row)
                      : col.accessor
                      ? String(row[col.accessor] ?? '')
                      : null}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
