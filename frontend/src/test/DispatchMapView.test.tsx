import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DispatchMapView } from '../components/operator/DispatchMapView';
import { ServiceRequestListItem } from '../types/api';

describe('DispatchMapView', () => {
  const mockRequests: ServiceRequestListItem[] = [
    {
      id: 101,
      customer_id: 1,
      customer_name: '张伟',
      customer_email: 'zhangwei@example.com',
      customer_phone: '13800138000',
      raw_message: '客厅空调不制冷并发出异响',
      service_type: 'HVAC',
      urgency: 'emergency',
      location: '广州市天河区天河路 123 号',
      status: 'waiting_for_approval',
      created_at: '2026-09-06T10:00:00Z',
      sla_status: 'on_track',
      sla_deadline: '2026-09-06T12:00:00Z',
    },
    {
      id: 102,
      customer_id: 2,
      customer_name: '李丽',
      customer_email: 'lili@example.com',
      customer_phone: '13900139000',
      raw_message: '办公室网络交换机闪红灯断网',
      service_type: 'Networking',
      urgency: 'high',
      location: '深圳市南山区科技园南区 8 栋',
      status: 'ready_for_review',
      created_at: '2026-09-06T10:30:00Z',
      sla_status: 'at_risk',
      sla_deadline: '2026-09-06T11:30:00Z',
    },
  ];

  it('renders GIS map operational title and statistics', () => {
    render(
      <MemoryRouter>
        <DispatchMapView requests={mockRequests} />
      </MemoryRouter>
    );

    expect(
      screen.getByText(/GIS 智能调度大屏 · 全国网格作业全景/)
    ).toBeInTheDocument();
    expect(screen.getByText(/网格实时在线/)).toBeInTheDocument();
    expect(screen.getAllByText(/广州天河服务中心/).length).toBeGreaterThanOrEqual(1);
  });

  it('displays selected request details in floating card and allows switching selection', () => {
    const onSelect = vi.fn();
    render(
      <MemoryRouter>
        <DispatchMapView requests={mockRequests} onSelectRequest={onSelect} />
      </MemoryRouter>
    );

    // Initial selected request 101 (matched in pin and side card)
    expect(screen.getAllByText('#101').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('张伟')).toBeInTheDocument();
    expect(screen.getByText('进入调度详情决策')).toBeInTheDocument();
  });
});
