import { apiClient } from './client';
import { AppointmentListItem, AppointmentDetail } from '../types/api';

export interface AppointmentFilterParams {
  status?: string;
  technician_id?: number;
  page?: number;
  limit?: number;
}

export async function fetchAppointments(
  params?: AppointmentFilterParams
): Promise<AppointmentListItem[]> {
  const searchParams = new URLSearchParams();
  if (params?.status && params.status !== 'all') {
    searchParams.set('status', params.status);
  }
  if (params?.technician_id) {
    searchParams.set('technician_id', params.technician_id.toString());
  }
  if (params?.page) {
    searchParams.set('page', params.page.toString());
  }
  if (params?.limit) {
    searchParams.set('limit', params.limit.toString());
  }

  const query = searchParams.toString();
  const endpoint = query ? `/appointments?${query}` : '/appointments';
  return apiClient<AppointmentListItem[]>(endpoint);
}

export async function fetchAppointmentDetail(
  id: number | string
): Promise<AppointmentDetail> {
  return apiClient<AppointmentDetail>(`/appointments/${id}`);
}

export async function startAppointment(id: number | string): Promise<any> {
  return apiClient(`/appointments/${id}/start`, {
    method: 'POST',
  });
}

export async function completeAppointment(
  id: number | string,
  payload?: { completion_notes?: string; resolution_summary?: string }
): Promise<any> {
  return apiClient(`/appointments/${id}/complete`, {
    method: 'POST',
    body: payload ? JSON.stringify(payload) : undefined,
  });
}

export async function cancelAppointment(
  id: number | string,
  reason?: string
): Promise<any> {
  return apiClient(`/appointments/${id}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

export async function reassignAppointment(
  id: number | string,
  payload?: { technician_id?: number; reason?: string }
): Promise<any> {
  return apiClient(`/appointments/${id}/reassign`, {
    method: 'POST',
    body: payload ? JSON.stringify(payload) : undefined,
  });
}

