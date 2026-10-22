import { useEffect, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router';
import { LoadingState } from '../components/feedback/LoadingState';
import {
  canUsePlatformConsole,
  isGranted,
  type PermissionRequirement,
} from '../session/permissions';
import { useSession } from '../session/useSession';

interface RequirePermissionProps {
  permission: PermissionRequirement;
  match?: 'all' | 'any';
  children: ReactNode;
}

export const FORBIDDEN_PATH = '/403';

/**
 * Route guard: renders children only when permitted, otherwise redirects to the 403 page.
 *
 * A platform page opened while a tenant (e.g. a mandated client) is active switches to the platform
 * console when the user's platform permissions grant it (deep link, bookmark, back button). The
 * reverse never happens: a tenant is only entered by an explicit choice in the switcher.
 */
export function RequirePermission({ permission, match = 'all', children }: RequirePermissionProps) {
  const { status, me, mode, hasPermission, setMode } = useSession();
  const location = useLocation();
  const granted = status === 'ready' && hasPermission(permission, match);
  const switchToPlatform =
    status === 'ready' &&
    !granted &&
    mode.kind === 'tenant' &&
    me !== null &&
    canUsePlatformConsole(me) &&
    isGranted(new Set(me.platform_permissions), permission, match);

  useEffect(() => {
    if (switchToPlatform) void setMode({ kind: 'platform' });
  }, [switchToPlatform, setMode]);

  if (status === 'loading') return <LoadingState label="Checking access" />;
  if (switchToPlatform) return <LoadingState label="Switching to the platform console" />;
  if (!granted) {
    return <Navigate to={FORBIDDEN_PATH} replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}
