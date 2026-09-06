import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { StatusBadge } from '../components/common/StatusBadge';

describe('StatusBadge', () => {
  it('renders SLA on_track badge correctly', () => {
    render(<StatusBadge type="sla" value="on_track" />);
    expect(screen.getByText('正常')).toBeInTheDocument();
  });

  it('renders SLA breached badge correctly', () => {
    render(<StatusBadge type="sla" value="breached" />);
    expect(screen.getByText('已超时')).toBeInTheDocument();
  });

  it('renders emergency urgency badge correctly', () => {
    render(<StatusBadge type="urgency" value="emergency" />);
    expect(screen.getByText('紧急')).toBeInTheDocument();
  });

  it('renders waiting_for_approval status badge correctly', () => {
    render(<StatusBadge type="status" value="waiting_for_approval" />);
    expect(screen.getByText('待确认派单')).toBeInTheDocument();
  });

  it('renders viewer role badge correctly', () => {
    render(<StatusBadge type="role" value="viewer" />);
    expect(screen.getByText('只读用户')).toBeInTheDocument();
  });
});
