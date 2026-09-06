import { describe, it, expect, beforeEach, vi } from 'vitest';
import { apiClient, ApiError } from '../api/client';

describe('apiClient', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('injects Bearer token from sessionStorage', async () => {
    sessionStorage.setItem('fieldops_auth_token', 'test-token-xyz');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok' }),
    });
    global.fetch = mockFetch;

    const result = await apiClient<{ status: string }>('/health');
    expect(result).toEqual({ status: 'ok' });
    expect(mockFetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/health',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer test-token-xyz',
          'Content-Type': 'application/json',
        }),
      })
    );
  });

  it('handles 409 Conflict with descriptive message', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({
        detail: 'The proposed appointment is no longer available and requires rescheduling.',
      }),
    });

    await expect(apiClient('/service-requests/1/approval', { method: 'POST' })).rejects.toThrow(
      'The proposed appointment is no longer available and requires rescheduling.'
    );
  });

  it('handles 401 Unauthorized by clearing storage and throwing ApiError', async () => {
    sessionStorage.setItem('fieldops_auth_token', 'expired-token');
    sessionStorage.setItem('fieldops_user', '{"role":"viewer"}');

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Token expired' }),
    });

    await expect(apiClient('/auth/me')).rejects.toThrow('Authentication required. Please log in.');
    expect(sessionStorage.getItem('fieldops_auth_token')).toBeNull();
    expect(sessionStorage.getItem('fieldops_user')).toBeNull();
  });

  it('handles 403 Forbidden with permission denied error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Forbidden' }),
    });

    await expect(apiClient('/admin/action')).rejects.toThrow(
      'Permission denied. Your role cannot perform this action.'
    );
  });
});
