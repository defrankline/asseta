import type { ReactNode } from 'react';
import { Route, Routes } from 'react-router';
import { PERMISSIONS } from '../access/permissionCodes';
import { RequirePermission } from '../access/RequirePermission';
import { AppShell } from '../layout/AppShell';
import { ROUTES } from '../navigation/routes';
import { ForbiddenPage } from '../pages/ForbiddenPage';
import { HomeRedirect } from '../pages/HomeRedirect';
import { MyAccessPage } from '../pages/MyAccessPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { PlatformDashboardPage } from '../pages/platform/dashboard/PlatformDashboardPage';
import { InvoicesPage } from '../pages/platform/invoices/InvoicesPage';
import { PaymentsPage } from '../pages/platform/payments/PaymentsPage';
import { TenantDetailPage } from '../pages/platform/tenantDetail/TenantDetailPage';
import { TenantsPage } from '../pages/platform/tenants/TenantsPage';
import { SystemStatusPage } from '../pages/SystemStatusPage';

function guard(permission: string, page: ReactNode) {
  return <RequirePermission permission={permission}>{page}</RequirePermission>;
}

/**
 * Every feature route must be wrapped in RequirePermission (deny by default).
 * Exceptions: My access (the user's own /me data), 403 and 404.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomeRedirect />} />
        <Route path={ROUTES.myAccess} element={<MyAccessPage />} />
        <Route
          path={ROUTES.platformDashboard}
          element={guard(PERMISSIONS.platformDashboardRead, <PlatformDashboardPage />)}
        />
        <Route
          path={ROUTES.platformTenants}
          element={guard(PERMISSIONS.platformTenantRead, <TenantsPage />)}
        />
        <Route
          path={ROUTES.platformTenantDetail}
          element={guard(PERMISSIONS.platformTenantRead, <TenantDetailPage />)}
        />
        <Route
          path={ROUTES.platformInvoices}
          element={guard(PERMISSIONS.platformInvoiceRead, <InvoicesPage />)}
        />
        <Route
          path={ROUTES.platformPayments}
          element={guard(PERMISSIONS.platformPaymentRead, <PaymentsPage />)}
        />
        <Route
          path={ROUTES.systemStatus}
          element={guard(PERMISSIONS.platformSystemRead, <SystemStatusPage />)}
        />
        <Route path={ROUTES.forbidden} element={<ForbiddenPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
