import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { User, Role } from '../types/auth';
import * as authApi from '../api/auth';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  role: Role | null;
  canAct: boolean;
  isAdmin: boolean;
  isOperator: boolean;
  isViewer: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(() => authApi.getStoredUser());
  const [token, setToken] = useState<string | null>(() => authApi.getStoredToken());
  // If user and token already exist in storage, we can start in authenticated state without blocking spinner
  const [isLoading, setIsLoading] = useState<boolean>(() => {
    const storedToken = authApi.getStoredToken();
    const storedUser = authApi.getStoredUser();
    return !!storedToken && !storedUser;
  });

  useEffect(() => {
    // Only revalidate session once on initial mount if a token is present
    const storedToken = authApi.getStoredToken();
    if (storedToken) {
      authApi.fetchCurrentUser()
        .then((fetchedUser) => {
          setUser(fetchedUser);
          sessionStorage.setItem('fieldops_user', JSON.stringify(fetchedUser));
        })
        .catch(() => {
          // Token invalid or expired
          authApi.clearAuth();
          setUser(null);
          setToken(null);
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, []);

  const handleLogin = async (username: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await authApi.login(username, password);
      queryClient.clear();
      setToken(res.access_token);
      setUser(res.user);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    authApi.clearAuth();
    queryClient.clear();
    setUser(null);
    setToken(null);
  };

  const role = user?.role || null;
  const isAuthenticated = !!user && !!token;
  const canAct = role === 'admin' || role === 'operator';
  const isAdmin = role === 'admin';
  const isOperator = role === 'operator';
  const isViewer = role === 'viewer';

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated,
        isLoading,
        role,
        canAct,
        isAdmin,
        isOperator,
        isViewer,
        login: handleLogin,
        logout: handleLogout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
