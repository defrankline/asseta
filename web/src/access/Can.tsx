import type { ReactNode } from 'react';
import type { PermissionRequirement } from '../session/permissions';
import { useSession } from '../session/useSession';

interface CanProps {
  permission: PermissionRequirement;
  /** `all` (default) requires every listed code; `any` requires at least one. */
  match?: 'all' | 'any';
  children: ReactNode;
  /** Rendered when denied; nothing by default. */
  fallback?: ReactNode;
}

/** Renders children only when the current mode grants the permission. Deny by default. */
export function Can({ permission, match = 'all', children, fallback = null }: CanProps) {
  const { status, hasPermission } = useSession();
  const allowed = status === 'ready' && hasPermission(permission, match);
  return <>{allowed ? children : fallback}</>;
}
