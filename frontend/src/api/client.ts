export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = sessionStorage.getItem('fieldops_auth_token');

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
    sessionStorage.removeItem('fieldops_auth_token');
    sessionStorage.removeItem('fieldops_user');
    // Only redirect if not already on login page
    if (window.location.pathname !== '/login') {
      window.location.href = '/login?expired=true';
    }
    throw new ApiError(401, 'Authentication required. Please log in.');
  }

  if (response.status === 403) {
    const errorBody = await response.json().catch(() => ({}));
    const detail =
      errorBody.detail && errorBody.detail !== 'Forbidden'
        ? errorBody.detail
        : 'Permission denied. Your role cannot perform this action.';
    throw new ApiError(403, detail, errorBody);
  }

  if (response.status === 409) {
    const errorBody = await response.json().catch(() => ({}));
    const detail = errorBody.detail || 'The proposed appointment is no longer available and requires rescheduling.';
    throw new ApiError(409, detail, errorBody);
  }

  if (response.status === 422) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiError(422, errorBody.detail || 'Invalid request payload format.', errorBody);
  }

  if (response.status === 503) {
    throw new ApiError(503, 'System temporarily unavailable. Please retry shortly.');
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const message = errorBody.detail || `Request failed with HTTP status ${response.status}`;
    throw new ApiError(response.status, message, errorBody);
  }

  // Handle empty bodies (204 No Content)
  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}
