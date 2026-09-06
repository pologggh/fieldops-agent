import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { AdminProtectedRoute } from '../routes/AdminProtectedRoute';
import { ConfirmDialog } from '../components/admin/ConfirmDialog';
import { PolicyDiffModal } from '../components/admin/PolicyDiffModal';
import * as authContext from '../auth/AuthContext';
import { DispatchPolicy } from '../types/admin';

const defaultAuthMock = {
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: false,
  role: null,
  canAct: false,
  isAdmin: false,
  isOperator: false,
  isViewer: false,
  login: vi.fn(),
  logout: vi.fn(),
};

describe('AdminProtectedRoute', () => {
  it('renders verifying spinner while checking session', () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      ...defaultAuthMock,
      isLoading: true,
    });

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <AdminProtectedRoute>
          <div>Admin Content</div>
        </AdminProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText(/正在验证系统管理员权限\.\.\./i)).toBeInTheDocument();
  });

  it('redirects unauthenticated user to /login', () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      ...defaultAuthMock,
      isAuthenticated: false,
      isLoading: false,
    });

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route
            path="/admin"
            element={
              <AdminProtectedRoute>
                <div>Admin Restricted Area</div>
              </AdminProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.queryByText('Admin Restricted Area')).not.toBeInTheDocument();
    expect(screen.getByText('Login Page')).toBeInTheDocument();
  });

  it('rejects operator and viewer with 403 Forbidden screen', () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      ...defaultAuthMock,
      user: { name: 'Dispatcher Bob', email: 'bob@fieldops.com', role: 'operator' },
      token: 'jwt-op-token',
      isAuthenticated: true,
      isLoading: false,
      role: 'operator',
      isOperator: true,
    });

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <AdminProtectedRoute>
          <div>Admin Restricted Area</div>
        </AdminProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.queryByText('Admin Restricted Area')).not.toBeInTheDocument();
    expect(screen.getByText(/403 - 无访问权限/i)).toBeInTheDocument();
    expect(screen.getByText(/您当前账号角色为/i)).toBeInTheDocument();
    expect(screen.getByText('调度员')).toBeInTheDocument();
    expect(screen.getByText(/返回调度控制台/i)).toBeInTheDocument();
  });

  it('allows access to users with role="admin"', () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      ...defaultAuthMock,
      user: { name: 'Super Admin', email: 'admin@fieldops.com', role: 'admin' },
      token: 'jwt-admin-token',
      isAuthenticated: true,
      isLoading: false,
      role: 'admin',
      isAdmin: true,
      canAct: true,
    });

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <AdminProtectedRoute>
          <div>Admin Governance Area</div>
        </AdminProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Admin Governance Area')).toBeInTheDocument();
  });
});

describe('ConfirmDialog', () => {
  it('renders confirmation message and handles confirm/cancel events', () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();

    render(
      <ConfirmDialog
        isOpen={true}
        title="确认停用工程师 陈志强？"
        message="停用前将自动校验未来预约排班。"
        confirmLabel="确认停用"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />
    );

    expect(screen.getByText('确认停用工程师 陈志强？')).toBeInTheDocument();
    expect(
      screen.getByText('停用前将自动校验未来预约排班。')
    ).toBeInTheDocument();

    fireEvent.click(screen.getByText('取消'));
    expect(onCancel).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText('确认停用'));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});

describe('PolicyDiffModal', () => {
  const activePolicy: DispatchPolicy = {
    id: 1,
    version: 1,
    is_active: true,
    weights: {
      workload_weight: 25,
      capacity_weight: 20,
      sla_weight: 30,
      travel_weight: 15,
      overtime_penalty: 10,
    },
    description: 'V1 initial weights',
    created_by: 'system',
    created_at: '2026-09-01T00:00:00Z',
  };

  const targetPolicy: DispatchPolicy = {
    id: 2,
    version: 2,
    is_active: false,
    weights: {
      workload_weight: 20,
      capacity_weight: 20,
      sla_weight: 40,
      travel_weight: 10,
      overtime_penalty: 10,
    },
    description: 'V2 higher SLA focus',
    created_by: 'admin@fieldops.com',
    created_at: '2026-09-02T00:00:00Z',
  };

  it('renders side-by-side weight comparison and delta calculations', () => {
    const onActivate = vi.fn();
    const onClose = vi.fn();

    render(
      <PolicyDiffModal
        isOpen={true}
        type="dispatch"
        activePolicy={activePolicy}
        targetPolicy={targetPolicy}
        onClose={onClose}
        onActivate={onActivate}
      />
    );

    expect(
      screen.getByText(/策略版本差异对比：目标版本 v2 vs 当前生效 \(v1\)/i)
    ).toBeInTheDocument();

    // sla_weight increased from 30% to 40% -> delta +10%
    expect(screen.getByText('+10%')).toBeInTheDocument();
    // workload_weight and travel_weight both decreased -> delta -5%
    expect(screen.getAllByText('-5%').length).toBe(2);

    const activateBtn = screen.getByText(/应用并切换为当前版本/i);
    fireEvent.click(activateBtn);
    expect(onActivate).toHaveBeenCalledTimes(1);

    const closeBtn = screen.getByText('关闭对比');
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
