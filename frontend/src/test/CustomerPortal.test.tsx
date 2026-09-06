import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CustomerProtectedRoute } from '../routes/CustomerProtectedRoute';
import { CustomerLayout } from '../components/customer/CustomerLayout';
import { CustomerLoginPage } from '../pages/customer/CustomerLoginPage';
import { CustomerRegisterPage } from '../pages/customer/CustomerRegisterPage';
import * as custAuthHook from '../auth/useCustomerAuth';
import { t } from '../locales';

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

describe('CustomerProtectedRoute', () => {
  it('renders loading spinner while authenticating customer', () => {
    vi.spyOn(custAuthHook, 'useCustomerAuth').mockReturnValue({
      customer: null,
      token: null,
      isAuthenticated: false,
      isLoading: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshProfile: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/customer']}>
        <CustomerProtectedRoute>
          <div>Customer Area</div>
        </CustomerProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText(new RegExp(t.auth.verifyingAccess, 'i'))).toBeInTheDocument();
  });

  it('redirects unauthenticated customer to /customer/login', () => {
    vi.spyOn(custAuthHook, 'useCustomerAuth').mockReturnValue({
      customer: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshProfile: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/customer']}>
        <Routes>
          <Route
            path="/customer"
            element={
              <CustomerProtectedRoute>
                <div>Customer Dashboard</div>
              </CustomerProtectedRoute>
            }
          />
          <Route path="/customer/login" element={<div>Customer Login View</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.queryByText('Customer Dashboard')).not.toBeInTheDocument();
    expect(screen.getByText('Customer Login View')).toBeInTheDocument();
  });

  it('renders child component for authenticated customer', () => {
    vi.spyOn(custAuthHook, 'useCustomerAuth').mockReturnValue({
      customer: { id: 1, name: 'Alice Customer', email: 'alice@example.com' },
      token: 'jwt-cust-token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshProfile: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/customer']}>
        <CustomerProtectedRoute>
          <div>Customer Area Allowed</div>
        </CustomerProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Customer Area Allowed')).toBeInTheDocument();
  });
});

describe('CustomerLayout & Navigation', () => {
  it('renders customer navbar with portal brand and customer links', () => {
    vi.spyOn(custAuthHook, 'useCustomerAuth').mockReturnValue({
      customer: { id: 1, name: 'Alice Customer', email: 'alice@example.com' },
      token: 'jwt-cust-token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshProfile: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/customer']}>
        <CustomerLayout />
      </MemoryRouter>
    );

    // Verify Customer Portal title and badge
    expect(screen.getByText('FieldOps')).toBeInTheDocument();
    expect(screen.getByText(t.navigation.portalSubtitle)).toBeInTheDocument();

    // Verify customer self-service navigation links
    expect(screen.getAllByText(t.navigation.overview)[0]).toBeInTheDocument();
    expect(screen.getAllByText(t.navigation.aiAssistant)[0]).toBeInTheDocument();
    expect(screen.getAllByText(t.navigation.myRequests)[0]).toBeInTheDocument();
    expect(screen.getAllByText(t.navigation.appointments)[0]).toBeInTheDocument();

    // Verify customer name displayed
    expect(screen.getByText('Alice Customer')).toBeInTheDocument();
  });
});

describe('CustomerLoginPage', () => {
  it('renders login form and demo fill button', () => {
    vi.spyOn(custAuthHook, 'useCustomerAuth').mockReturnValue({
      customer: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshProfile: vi.fn(),
    });

    render(
      <MemoryRouter>
        <CustomerLoginPage />
      </MemoryRouter>
    );

    expect(screen.getByText(t.auth.loginTitle)).toBeInTheDocument();
    expect(screen.getByPlaceholderText('请输入注册邮箱')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('请输入密码')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /填入演示客户账号/ })).toBeInTheDocument();
  });

  it('populates demo credentials when demo button is clicked', () => {
    vi.spyOn(custAuthHook, 'useCustomerAuth').mockReturnValue({
      customer: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshProfile: vi.fn(),
    });

    render(
      <MemoryRouter>
        <CustomerLoginPage />
      </MemoryRouter>
    );

    const fillButton = screen.getByRole('button', { name: /填入演示客户账号/ });
    fireEvent.click(fillButton);

    const emailInput = screen.getByPlaceholderText('请输入注册邮箱') as HTMLInputElement;
    expect(emailInput.value).toBe('alice.test@example.com');
  });
});

describe('CustomerRegisterPage', () => {
  it('renders registration fields and submit button', () => {
    vi.spyOn(custAuthHook, 'useCustomerAuth').mockReturnValue({
      customer: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshProfile: vi.fn(),
    });

    render(
      <MemoryRouter>
        <CustomerRegisterPage />
      </MemoryRouter>
    );

    expect(screen.getByText(t.auth.registerTitle)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(t.auth.fullNamePlaceholder)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(t.auth.emailPlaceholder)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(t.auth.passwordHint)).toBeInTheDocument();
  });
});
