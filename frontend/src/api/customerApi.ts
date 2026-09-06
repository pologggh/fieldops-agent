import { ApiError } from './client';
import {
  CustomerAppointmentView,
  CustomerAuthResponse,
  CustomerHomeSummary,
  CustomerLoginInput,
  CustomerProfile,
  CustomerProfileUpdateInput,
  CustomerRegisterInput,
  CustomerRescheduleInput,
  CustomerServiceRequestCancelInput,
  CustomerServiceRequestCreateInput,
  CustomerServiceRequestSupplementInput,
  CustomerServiceRequestView,
  CustomerUser,
  ConversationConfirmResponse,
  ConversationCreateInput,
  ConversationSendMessageInput,
  ConversationSummaryItem,
  ConversationView,
} from '../types/customer';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export function getStoredCustomerToken(): string | null {
  return sessionStorage.getItem('fieldops_customer_token');
}

export function getStoredCustomer(): CustomerUser | null {
  const raw = sessionStorage.getItem('fieldops_customer');
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function clearCustomerAuth(): void {
  sessionStorage.removeItem('fieldops_customer_token');
  sessionStorage.removeItem('fieldops_customer');
}

export async function customerApiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredCustomerToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err: any) {
    throw new ApiError(0, 'Network connection failed. Backend server may be offline.', err);
  }

  if (response.status === 401) {
    clearCustomerAuth();
    if (window.location.pathname !== '/customer/login' && window.location.pathname !== '/customer/register') {
      window.location.href = '/customer/login?expired=true';
    }
    throw new ApiError(401, 'Session expired. Please log in again.');
  }

  if (response.status === 403) {
    throw new ApiError(403, 'Permission denied.');
  }

  if (response.status === 404) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiError(404, errorBody.detail || 'Record not found.', errorBody);
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const message = errorBody.detail || `Request failed with HTTP status ${response.status}`;
    throw new ApiError(response.status, message, errorBody);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

// Authentication
export async function registerCustomer(input: CustomerRegisterInput): Promise<CustomerAuthResponse> {
  const res = await customerApiClient<CustomerAuthResponse>('/customer-auth/register', {
    method: 'POST',
    body: JSON.stringify(input),
  });
  sessionStorage.setItem('fieldops_customer_token', res.access_token);
  sessionStorage.setItem('fieldops_customer', JSON.stringify(res.customer));
  return res;
}

export async function loginCustomer(input: CustomerLoginInput): Promise<CustomerAuthResponse> {
  const res = await customerApiClient<CustomerAuthResponse>('/customer-auth/login', {
    method: 'POST',
    body: JSON.stringify(input),
  });
  sessionStorage.setItem('fieldops_customer_token', res.access_token);
  sessionStorage.setItem('fieldops_customer', JSON.stringify(res.customer));
  return res;
}

// Profile
export async function fetchCustomerProfile(): Promise<CustomerProfile> {
  return customerApiClient<CustomerProfile>('/customer/me');
}

export async function updateCustomerProfile(input: CustomerProfileUpdateInput): Promise<CustomerProfile> {
  return customerApiClient<CustomerProfile>('/customer/me', {
    method: 'PATCH',
    body: JSON.stringify(input),
  });
}

// Summary
export async function fetchCustomerSummary(): Promise<CustomerHomeSummary> {
  return customerApiClient<CustomerHomeSummary>('/customer/summary');
}

// Requests
export async function fetchCustomerRequests(statusFilter?: string): Promise<CustomerServiceRequestView[]> {
  const query = statusFilter && statusFilter !== 'all' ? `?status_filter=${encodeURIComponent(statusFilter)}` : '';
  return customerApiClient<CustomerServiceRequestView[]>(`/customer/requests${query}`);
}

export async function fetchCustomerRequest(id: number): Promise<CustomerServiceRequestView> {
  return customerApiClient<CustomerServiceRequestView>(`/customer/requests/${id}`);
}

export async function createCustomerRequest(
  input: CustomerServiceRequestCreateInput
): Promise<CustomerServiceRequestView> {
  return customerApiClient<CustomerServiceRequestView>('/customer/requests', {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export async function supplementCustomerRequest(
  id: number,
  input: CustomerServiceRequestSupplementInput
): Promise<CustomerServiceRequestView> {
  return customerApiClient<CustomerServiceRequestView>(`/customer/requests/${id}/supplement`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export async function cancelCustomerRequest(
  id: number,
  input: CustomerServiceRequestCancelInput
): Promise<CustomerServiceRequestView> {
  return customerApiClient<CustomerServiceRequestView>(`/customer/requests/${id}/cancel`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export async function rescheduleCustomerRequest(
  id: number,
  input: CustomerRescheduleInput
): Promise<CustomerServiceRequestView> {
  return customerApiClient<CustomerServiceRequestView>(`/customer/requests/${id}/reschedule`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

// Appointments
export async function fetchCustomerAppointments(statusFilter?: string): Promise<CustomerAppointmentView[]> {
  const query = statusFilter && statusFilter !== 'all' ? `?status_filter=${encodeURIComponent(statusFilter)}` : '';
  return customerApiClient<CustomerAppointmentView[]>(`/customer/appointments${query}`);
}

export async function fetchCustomerAppointment(id: number): Promise<CustomerAppointmentView> {
  return customerApiClient<CustomerAppointmentView>(`/customer/appointments/${id}`);
}

export async function cancelCustomerAppointment(
  id: number,
  reason?: string
): Promise<CustomerAppointmentView> {
  return customerApiClient<CustomerAppointmentView>(`/customer/appointments/${id}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ reason: reason || 'Customer requested cancellation' }),
  });
}

// =============================================================================
// Conversational Agent API (Phase 22)
// =============================================================================

export async function createConversation(input?: ConversationCreateInput): Promise<ConversationView> {
  return customerApiClient<ConversationView>('/customer/conversations', {
    method: 'POST',
    body: JSON.stringify(input || {}),
  });
}

export async function fetchConversations(statusFilter?: string): Promise<ConversationSummaryItem[]> {
  const query = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : '';
  return customerApiClient<ConversationSummaryItem[]>(`/customer/conversations${query}`);
}

export async function fetchConversation(id: number): Promise<ConversationView> {
  return customerApiClient<ConversationView>(`/customer/conversations/${id}`);
}

export async function sendConversationMessage(
  id: number,
  input: ConversationSendMessageInput
): Promise<ConversationView> {
  return customerApiClient<ConversationView>(`/customer/conversations/${id}/messages`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export async function confirmConversation(
  id: number,
  idempotencyKey?: string
): Promise<ConversationConfirmResponse> {
  return customerApiClient<ConversationConfirmResponse>(`/customer/conversations/${id}/confirm`, {
    method: 'POST',
    body: JSON.stringify({ idempotency_key: idempotencyKey }),
  });
}

export async function cancelConversation(id: number): Promise<ConversationView> {
  return customerApiClient<ConversationView>(`/customer/conversations/${id}/cancel`, {
    method: 'POST',
  });
}

