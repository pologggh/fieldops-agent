import { apiClient } from './client';
import { EscalationItem, EscalationDetail } from '../types/api';

export interface EscalationFilterParams {
  severity?: string;
  status?: string;
  page?: number;
  limit?: number;
}

export async function fetchEscalations(
  params?: EscalationFilterParams
): Promise<EscalationItem[]> {
  const searchParams = new URLSearchParams();
  if (params?.severity && params.severity !== 'all') {
    searchParams.set('severity', params.severity);
  }
  if (params?.status && params.status !== 'all') {
    searchParams.set('status', params.status);
  }
  if (params?.page) {
    searchParams.set('page', params.page.toString());
  }
  if (params?.limit) {
    searchParams.set('limit', params.limit.toString());
  }

  const query = searchParams.toString();
  const endpoint = query ? `/escalations?${query}` : '/escalations';
  return apiClient<EscalationItem[]>(endpoint);
}

export async function fetchEscalationDetail(
  id: number | string
): Promise<EscalationDetail> {
  return apiClient<EscalationDetail>(`/escalations/${id}`);
}

export async function acknowledgeEscalation(id: number | string): Promise<any> {
  return apiClient(`/escalations/${id}/acknowledge`, {
    method: 'POST',
  });
}

export async function resolveEscalation(id: number | string): Promise<any> {
  return apiClient(`/escalations/${id}/resolve`, {
    method: 'POST',
  });
}
