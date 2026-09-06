import { apiClient } from './client';
import { DashboardSummary } from '../types/api';

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  return apiClient<DashboardSummary>('/dashboard/summary');
}
