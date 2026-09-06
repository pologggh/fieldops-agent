import { apiClient } from './client';
import {
  ServiceRequestListItem,
  ServiceRequestDetail,
} from '../types/api';

export interface ServiceRequestFilterParams {
  status?: string;
  urgency?: string;
  page?: number;
  limit?: number;
}

export async function fetchServiceRequests(
  params?: ServiceRequestFilterParams
): Promise<ServiceRequestListItem[]> {
  const searchParams = new URLSearchParams();
  if (params?.status && params.status !== 'all') {
    searchParams.set('status', params.status);
  }
  if (params?.urgency && params.urgency !== 'all') {
    searchParams.set('urgency', params.urgency);
  }
  if (params?.page) {
    searchParams.set('page', params.page.toString());
  }
  if (params?.limit) {
    searchParams.set('limit', params.limit.toString());
  }

  const query = searchParams.toString();
  const endpoint = query ? `/service-requests?${query}` : '/service-requests';
  const data = await apiClient<any>(endpoint);
  if (data && Array.isArray(data.items)) {
    return data.items;
  }
  if (Array.isArray(data)) {
    return data;
  }
  return [];
}

export async function fetchServiceRequestDetail(
  id: number | string
): Promise<ServiceRequestDetail> {
  return apiClient<ServiceRequestDetail>(`/service-requests/${id}`);
}

export interface ApprovalPayload {
  decision: 'approve' | 'reject';
  reason?: string;
}

export interface ApprovalResult {
  request_id: string;
  service_request_id?: number;
  workflow_status: string;
  approval_status?: string;
  approval_reason?: string;
  appointment_id?: number;
  appointment_status?: string;
}

export async function submitApproval(
  requestId: number | string,
  payload: ApprovalPayload
): Promise<ApprovalResult> {
  return apiClient<ApprovalResult>(`/service-requests/${requestId}/approval`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
