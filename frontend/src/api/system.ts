import { apiClient } from './client';
import { SystemStatus } from '../types/api';

export async function fetchSystemStatus(): Promise<SystemStatus> {
  return apiClient<SystemStatus>('/system/status');
}
