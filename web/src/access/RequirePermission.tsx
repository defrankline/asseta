import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router';
import { LoadingState } from '../components/feedback/LoadingState';
import type { PermissionRequirement } from '../session/permissions';
import { useSession } from '../session/useSession';

interface RequirePermissionProps {
  permission: PermissionRequirement;
  match?: 'all' | 'any';
  children: ReactNode;
}

export const FORBIDDEN_PATH = '/403';

/** Route guard: renders children only when permitted, otherwise redirects to the 403 page. */
export function RequirePermission({ permission, match = 'all', children }: RequirePermissionProps) {
  const { status, hasPermission } = useSession();
  const location = useLocation();
  if (status === 'loading') return <LoadingState label="Checking access" />;
  if (status !== 'ready' || !hasPermission(permission, match)) {
    return <Navigate to={FORBIDDEN_PATH} replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}
