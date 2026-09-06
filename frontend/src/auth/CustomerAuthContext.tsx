import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { CustomerUser, CustomerLoginInput, CustomerRegisterInput } from '../types/customer';
import * as customerApi from '../api/customerApi';

interface CustomerAuthContextType {
  customer: CustomerUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (input: CustomerLoginInput) => Promise<void>;
  register: (input: CustomerRegisterInput) => Promise<void>;
  logout: () => void;
  refreshProfile: () => Promise<void>;
}

const CustomerAuthContext = createContext<CustomerAuthContextType | undefined>(undefined);

export function CustomerAuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [customer, setCustomer] = useState<CustomerUser | null>(() => customerApi.getStoredCustomer());
  const [token, setToken] = useState<string | null>(() => customerApi.getStoredCustomerToken());
  const [isLoading, setIsLoading] = useState<boolean>(() => {
    const storedToken = customerApi.getStoredCustomerToken();
    const storedCust = customerApi.getStoredCustomer();
    return !!storedToken && !storedCust;
  });

  const refreshProfile = async () => {
    try {
      const profile = await customerApi.fetchCustomerProfile();
      const updatedUser: CustomerUser = {
        id: profile.id,
        email: profile.email,
        name: profile.name,
        phone: profile.phone,
        address: profile.address,
      };
      setCustomer(updatedUser);
      sessionStorage.setItem('fieldops_customer', JSON.stringify(updatedUser));
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    const storedToken = customerApi.getStoredCustomerToken();
    if (storedToken) {
      refreshProfile().finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const handleLogin = async (input: CustomerLoginInput) => {
    setIsLoading(true);
    try {
      const res = await customerApi.loginCustomer(input);
      queryClient.clear();
      setToken(res.access_token);
      setCustomer(res.customer);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (input: CustomerRegisterInput) => {
    setIsLoading(true);
    try {
      const res = await customerApi.registerCustomer(input);
      queryClient.clear();
      setToken(res.access_token);
      setCustomer(res.customer);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    customerApi.clearCustomerAuth();
    queryClient.clear();
    setCustomer(null);
    setToken(null);
  };

  const isAuthenticated = !!customer && !!token;

  return (
    <CustomerAuthContext.Provider
      value={{
        customer,
        token,
        isAuthenticated,
        isLoading,
        login: handleLogin,
        register: handleRegister,
        logout: handleLogout,
        refreshProfile,
      }}
    >
      {children}
    </CustomerAuthContext.Provider>
  );
}

export function useCustomerAuth(): CustomerAuthContextType {
  const context = useContext(CustomerAuthContext);
  if (!context) {
    throw new Error('useCustomerAuth must be used within a CustomerAuthProvider');
  }
  return context;
}
