import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ProtectedRoute } from './ProtectedRoute';
import { DashboardLayout } from '../components/layout/DashboardLayout';

import { LoginPage } from '../pages/LoginPage';
import { OverviewPage } from '../pages/OverviewPage';
import { ServiceRequestsPage } from '../pages/ServiceRequestsPage';
import { ServiceRequestDetailPage } from '../pages/ServiceRequestDetailPage';
import { AppointmentsPage } from '../pages/AppointmentsPage';
import { AppointmentDetailPage } from '../pages/AppointmentDetailPage';
import { EscalationsPage } from '../pages/EscalationsPage';
import { EscalationDetailPage } from '../pages/EscalationDetailPage';
import { SystemStatusPage } from '../pages/SystemStatusPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { ForbiddenPage } from '../pages/ForbiddenPage';
import { ServiceUnavailablePage } from '../pages/ServiceUnavailablePage';

// Customer Portal Imports
import { CustomerProtectedRoute } from './CustomerProtectedRoute';
import { CustomerLayout } from '../components/customer/CustomerLayout';
import { CustomerLoginPage } from '../pages/customer/CustomerLoginPage';
import { CustomerRegisterPage } from '../pages/customer/CustomerRegisterPage';
import { CustomerHomePage } from '../pages/customer/CustomerHomePage';
import { CustomerRequestServicePage } from '../pages/customer/CustomerRequestServicePage';
import { CustomerRequestsPage } from '../pages/customer/CustomerRequestsPage';
import { CustomerRequestDetailPage } from '../pages/customer/CustomerRequestDetailPage';
import { CustomerAppointmentsPage } from '../pages/customer/CustomerAppointmentsPage';
import { CustomerAppointmentDetailPage } from '../pages/customer/CustomerAppointmentDetailPage';
import { CustomerProfilePage } from '../pages/customer/CustomerProfilePage';
import { CustomerAssistantPage } from '../pages/customer/CustomerAssistantPage';

// Admin Console Imports
import { AdminProtectedRoute } from './AdminProtectedRoute';
import { AdminLayout } from '../components/admin/AdminLayout';
import { AdminOverviewPage } from '../pages/admin/AdminOverviewPage';
import { AdminUsersPage } from '../pages/admin/AdminUsersPage';
import { AdminTechniciansPage } from '../pages/admin/AdminTechniciansPage';
import { AdminDispatchPolicyPage } from '../pages/admin/AdminDispatchPolicyPage';
import { AdminSLAPolicyPage } from '../pages/admin/AdminSLAPolicyPage';
import { AdminIntegrationsPage } from '../pages/admin/AdminIntegrationsPage';
import { AdminBranchesPage } from '../pages/admin/AdminBranchesPage';
import { AdminTeamsPage } from '../pages/admin/AdminTeamsPage';
import { AdminAuditPage } from '../pages/admin/AdminAuditPage';
import { AdminSystemPage } from '../pages/admin/AdminSystemPage';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Error & Global Fallback Routes */}
      <Route path="/forbidden" element={<ForbiddenPage />} />
      <Route path="/unavailable" element={<ServiceUnavailablePage />} />

      {/* Customer Portal Public Auth */}
      <Route path="/customer/login" element={<CustomerLoginPage />} />
      <Route path="/customer/register" element={<CustomerRegisterPage />} />

      {/* Customer Portal Protected Area */}
      <Route
        path="/customer"
        element={
          <CustomerProtectedRoute>
            <CustomerLayout />
          </CustomerProtectedRoute>
        }
      >
        <Route index element={<CustomerHomePage />} />
        <Route path="requests" element={<CustomerRequestsPage />} />
        <Route path="requests/new" element={<CustomerRequestServicePage />} />
        <Route path="requests/:id" element={<CustomerRequestDetailPage />} />
        <Route path="appointments" element={<CustomerAppointmentsPage />} />
        <Route path="appointments/:id" element={<CustomerAppointmentDetailPage />} />
        <Route path="profile" element={<CustomerProfilePage />} />
        <Route path="assistant" element={<CustomerAssistantPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      {/* Operator Dashboard Public Auth */}
      <Route path="/login" element={<LoginPage />} />

      {/* Operator Dashboard Protected Area */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<OverviewPage />} />
        <Route path="service-requests" element={<ServiceRequestsPage />} />
        <Route path="service-requests/:id" element={<ServiceRequestDetailPage />} />
        <Route path="appointments" element={<AppointmentsPage />} />
        <Route path="appointments/:id" element={<AppointmentDetailPage />} />
        <Route path="escalations" element={<EscalationsPage />} />
        <Route path="escalations/:id" element={<EscalationDetailPage />} />
        <Route path="system" element={<SystemStatusPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      {/* Admin Console Protected Area (Admin Role Only) */}
      <Route
        path="/admin"
        element={
          <AdminProtectedRoute>
            <AdminLayout />
          </AdminProtectedRoute>
        }
      >
        <Route index element={<AdminOverviewPage />} />
        <Route path="users" element={<AdminUsersPage />} />
        <Route path="branches" element={<AdminBranchesPage />} />
        <Route path="teams" element={<AdminTeamsPage />} />
        <Route path="technicians" element={<AdminTechniciansPage />} />
        <Route path="policies/dispatch" element={<AdminDispatchPolicyPage />} />
        <Route path="policies/sla" element={<AdminSLAPolicyPage />} />
        <Route path="integrations" element={<AdminIntegrationsPage />} />
        <Route path="audit" element={<AdminAuditPage />} />
        <Route path="system" element={<AdminSystemPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      {/* Fallback redirect to 404 */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
};
