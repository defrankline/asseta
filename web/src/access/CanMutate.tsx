import type { ReactNode } from 'react';
import type { PermissionRequirement } from '../session/permissions';
import { useSession } from '../session/useSession';

interface CanMutateProps {
  permission: PermissionRequirement;
  match?: 'all' | 'any';
  children: ReactNode;
  fallback?: ReactNode;
}

/**
 * Like `<Can>`, for mutating actions: also hidden while the active tenant is READ_ONLY
 * (subscription grace/suspension). The API remains authoritative.
 */
export function CanMutate({
  permission,
  match = 'all',
  children,
  fallback = null,
}: CanMutateProps) {
  const { status, hasPermission, isReadOnly } = useSession();
  const allowed = status === 'ready' && !isReadOnly && hasPermission(permission, match);
  return <>{allowed ? children : fallback}</>;
}
