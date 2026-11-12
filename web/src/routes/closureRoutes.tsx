import { Navigate, Route } from 'react-router';
import type { ReactNode } from 'react';
import { PERMISSIONS } from '../access/permissionCodes';
import { ROUTES } from '../navigation/routes';
import { CloseCompanyPage, DeletionRequestDetailPage, DeletionRequestsPage } from './lazyPages';

type Guard = (permission: string, page: ReactNode) => ReactNode;

/**
 * Company closure (Administration -> Close company), platform deletion requests (Tenants -> Deletion
 * requests) and the signed-out landing after a personal account deletion.
 */
export function closureRouteElements(guard: Guard): ReactNode[] {
  const routes: [string, string, ReactNode][] = [
    [ROUTES.tenantCompanyClose, PERMISSIONS.tenantCompanyClose, <CloseCompanyPage key="c" />],
    [
      ROUTES.platformDeletionRequests,
      PERMISSIONS.platformTenantDeletionRead,
      <DeletionRequestsPage key="l" />,
    ],
    [
      ROUTES.platformDeletionRequestDetail,
      PERMISSIONS.platformTenantDeletionRead,
      <DeletionRequestDetailPage key="d" />,
    ],
  ];
  return [
    ...routes.map(([path, permission, element]) => (
      <Route key={path} path={path} element={guard(permission, element)} />
    )),
    // Signing in again from the signed-out page lands here: go home.
    <Route
      key="signed-out"
      path={ROUTES.signedOut}
      element={<Navigate to={ROUTES.home} replace />}
    />,
  ];
}
