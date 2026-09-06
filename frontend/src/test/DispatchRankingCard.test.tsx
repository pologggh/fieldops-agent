import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { DispatchRankingCard } from '../components/features/DispatchRankingCard';
import { DispatchCandidate } from '../types/api';

describe('DispatchRankingCard', () => {
  const mockCandidate: DispatchCandidate = {
    rank: 1,
    technician_id: 101,
    name: '陈志强',
    service_area: '广州天河区',
    skills: ['HVAC', 'Electrical'],
    score: 0.95,
    availability: '今日在岗',
    workload: 0,
    capacity: '今日已排 0 单',
    sla_fit: '极佳',
    travel_estimate: '距现场约 15 分钟',
    reasons: [
      '主营技能完全符合：空调暖通',
      '常驻辖区覆盖目标地址：广州天河区',
      '当前空闲度极佳：今日已排工单 0 单',
    ],
  };

  it('renders technician info, rank, and match score', () => {
    render(<DispatchRankingCard candidate={mockCandidate} isTopChoice={true} />);

    expect(screen.getByText('陈志强')).toBeInTheDocument();
    expect(screen.getByText('推荐服务工程师')).toBeInTheDocument();
    expect(screen.getByText(/综合匹配第 1 名/)).toBeInTheDocument();
    expect(screen.getByText('95')).toBeInTheDocument();
    expect(screen.getByText('广州天河区')).toBeInTheDocument();
    expect(screen.getByText('HVAC')).toBeInTheDocument();
    expect(screen.getByText('Electrical')).toBeInTheDocument();
  });

  it('renders explainable reasons for top candidate', () => {
    render(<DispatchRankingCard candidate={mockCandidate} isTopChoice={true} />);

    expect(screen.getByText('推荐依据与决策说明')).toBeInTheDocument();
    expect(screen.getByText('主营技能完全符合：空调暖通')).toBeInTheDocument();
    expect(screen.getByText('常驻辖区覆盖目标地址：广州天河区')).toBeInTheDocument();
  });
});
