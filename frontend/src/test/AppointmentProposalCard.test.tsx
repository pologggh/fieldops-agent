import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AppointmentProposalCard } from '../components/features/AppointmentProposalCard';
import { AppointmentProposal } from '../types/api';
import * as authHook from '../auth/useAuth';

describe('AppointmentProposalCard', () => {
  const mockProposal: AppointmentProposal = {
    technician_id: 1,
    technician_name: '陈志强',
    start_time: '2026-09-04T10:00:00Z',
    end_time: '2026-09-04T12:00:00Z',
    service_request_id: 1,
    service_type: 'HVAC',
    location: '广州天河区',
    dispatch_reason: '持有高空与暖通资质，距离近且当前无在手任务',
  };

  it('renders proposal details correctly', () => {
    vi.spyOn(authHook, 'useAuth').mockReturnValue({
      user: { name: '调度员', email: 'op@test.com', role: 'operator' },
      token: 'fake',
      isAuthenticated: true,
      isLoading: false,
      role: 'operator',
      canAct: true,
      isAdmin: false,
      isOperator: true,
      isViewer: false,
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <AppointmentProposalCard
        proposal={mockProposal}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />
    );

    expect(screen.getByText('陈志强')).toBeInTheDocument();
    expect(screen.getByText('空调 / 暖通维修')).toBeInTheDocument();
    expect(screen.getByText('广州天河区')).toBeInTheDocument();
    expect(screen.getByText(/持有高空与暖通资质/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /确认派单并预约/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /协商改派/i })).toBeInTheDocument();
  });

  it('triggers onApprove when operator clicks approve', async () => {
    const onApproveMock = vi.fn().mockResolvedValue(undefined);

    vi.spyOn(authHook, 'useAuth').mockReturnValue({
      user: { name: '调度员', email: 'op@test.com', role: 'operator' },
      token: 'fake',
      isAuthenticated: true,
      isLoading: false,
      role: 'operator',
      canAct: true,
      isAdmin: false,
      isOperator: true,
      isViewer: false,
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <AppointmentProposalCard
        proposal={mockProposal}
        onApprove={onApproveMock}
        onReject={vi.fn()}
      />
    );

    const approveBtn = screen.getByRole('button', { name: /确认派单并预约/i });
    fireEvent.click(approveBtn);

    expect(onApproveMock).toHaveBeenCalled();
  });

  it('hides action buttons and shows read-only mode for Viewer role', () => {
    vi.spyOn(authHook, 'useAuth').mockReturnValue({
      user: { name: '只读用户', email: 'viewer@test.com', role: 'viewer' },
      token: 'fake',
      isAuthenticated: true,
      isLoading: false,
      role: 'viewer',
      canAct: false,
      isAdmin: false,
      isOperator: false,
      isViewer: true,
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <AppointmentProposalCard
        proposal={mockProposal}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />
    );

    expect(screen.queryByRole('button', { name: /确认派单并预约/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /协商改派/i })).not.toBeInTheDocument();
    expect(screen.getByText(/只读角色：仅具备查看权限/i)).toBeInTheDocument();
  });

  it('displays 409 Conflict error banner with required rescheduling message', () => {
    vi.spyOn(authHook, 'useAuth').mockReturnValue({
      user: { name: '调度员', email: 'op@test.com', role: 'operator' },
      token: 'fake',
      isAuthenticated: true,
      isLoading: false,
      role: 'operator',
      canAct: true,
      isAdmin: false,
      isOperator: true,
      isViewer: false,
      login: vi.fn(),
      logout: vi.fn(),
    });

    const conflictMsg = '建议的上门预约时隙已被占用，需要重新协商调度。';

    render(
      <AppointmentProposalCard
        proposal={mockProposal}
        errorMessage={conflictMsg}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(conflictMsg)).toBeInTheDocument();
  });

  it('disables buttons during isSubmitting to prevent double clicks', () => {
    vi.spyOn(authHook, 'useAuth').mockReturnValue({
      user: { name: '调度员', email: 'op@test.com', role: 'operator' },
      token: 'fake',
      isAuthenticated: true,
      isLoading: false,
      role: 'operator',
      canAct: true,
      isAdmin: false,
      isOperator: true,
      isViewer: false,
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <AppointmentProposalCard
        proposal={mockProposal}
        isSubmitting={true}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />
    );

    const approveBtn = screen.getByRole('button', { name: /正在锁定派工/i });
    expect(approveBtn).toBeDisabled();
  });
});
