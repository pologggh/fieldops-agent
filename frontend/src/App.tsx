import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './auth/AuthContext';
import { CustomerAuthProvider } from './auth/CustomerAuthContext';
import { ToastProvider } from './components/ui/ToastContext';
import { AppRoutes } from './routes/AppRoutes';

import { ErrorBoundary } from './components/common/ErrorBoundary';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5000,
    },
  },
});

export const App: React.FC = () => {
  return (
    <ErrorBoundary fallbackTitle="FieldOps 现场操作平台">
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <CustomerAuthProvider>
              <ToastProvider>
                <AppRoutes />
              </ToastProvider>
            </CustomerAuthProvider>
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
};

export default App;
