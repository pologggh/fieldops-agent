import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProtectedRoute } from '../routes/ProtectedRoute';
import * as authHook from '../auth/useAuth';

describe('ProtectedRoute', () => {
  it('renders loading spinner while checking auth session', () => {
    vi.spyOn(authHook, 'useAuth').mockReturnValue({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: true,
      role: null,
      canAct: false,
      isAdmin: false,
      isOperator: false,
      isViewer: false,
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByRole('status', { name: /Authenticating session\.\.\./i })).toBeInTheDocument();
  });

  it('redirects to /login when unauthenticated', () => {
    vi.spyOn(authHook, 'useAuth').mockReturnValue({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      role: null,
      canAct: false,
      isAdmin: false,
      isOperator: false,
      isViewer: false,
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <div>Secret Dashboard</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.queryByText('Secret Dashboard')).not.toBeInTheDocument();
    expect(screen.getByText('Login Page')).toBeInTheDocument();
  });

  it('renders child component when authenticated', () => {
    vi.spyOn(authHook, 'useAuth').mockReturnValue({
      user: { name: 'Admin', email: 'admin@test.com', role: 'admin' },
      token: 'valid-token',
      isAuthenticated: true,
      isLoading: false,
      role: 'admin',
      canAct: true,
      isAdmin: true,
      isOperator: false,
      isViewer: false,
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <ProtectedRoute>
          <div>Secret Dashboard</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Secret Dashboard')).toBeInTheDocument();
  });
});
