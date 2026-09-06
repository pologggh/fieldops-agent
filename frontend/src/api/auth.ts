import { apiClient } from './client';
import { AuthResponse, User } from '../types/auth';

export async function login(username: string, password: string): Promise<AuthResponse> {
  const response = await apiClient<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  sessionStorage.setItem('fieldops_auth_token', response.access_token);
  sessionStorage.setItem('fieldops_user', JSON.stringify(response.user));
  return response;
}

export async function fetchCurrentUser(): Promise<User> {
  return apiClient<User>('/auth/me');
}

export function getStoredUser(): User | null {
  const raw = sessionStorage.getItem('fieldops_user');
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function getStoredToken(): string | null {
  return sessionStorage.getItem('fieldops_auth_token');
}

export function clearAuth(): void {
  sessionStorage.removeItem('fieldops_auth_token');
  sessionStorage.removeItem('fieldops_user');
}
