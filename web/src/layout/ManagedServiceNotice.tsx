import { Alert, Link } from '@mui/material';
import { useCallback } from 'react';
import { Link as RouterLink, useLocation } from 'react-router';
import { PERMISSIONS } from '../access/permissionCodes';
import { managedServiceService } from '../api/services/managedServiceService';
import { useAsyncResource } from '../hooks/useAsyncResource';
import { ROUTES } from '../navigation/routes';
import { isMandated } from '../session/permissions';
import { useSession } from '../session/useSession';

const NOTICE_STATUSES: ReadonlySet<string> = new Set(['IN_FORCE', 'SCHEDULED']);

/**
 * Tells the client's own administrators that Asseta holds a managed-service mandate over this
 * account. Loaded once per tenant switch; any failure simply hides the notice.
 */
export function ManagedServiceNotice() {
  const { mode, activeTenant, hasPermission } = useSession();
  const { pathname } = useLocation();
  const tenantId = mode.kind === 'tenant' ? mode.tenantId : null;
  const enabled =
    tenantId !== null &&
    activeTenant !== null &&
    activeTenant.access_state !== 'BLOCKED' &&
    !isMandated(activeTenant) &&
    hasPermission(PERMISSIONS.tenantManagedServiceRead);
  const load = useCallback((signal: AbortSignal) => managedServiceService.get(signal), []);
  const { data, loading, error } = useAsyncResource(load, [tenantId], enabled);

  const mandate = data?.mandate ?? null;
  if (!enabled || loading || error !== null || mandate === null) return null;
  if (!NOTICE_STATUSES.has(mandate.status) || pathname === ROUTES.tenantManagedService) return null;

  return (
    <Alert severity="info" className="mb-4" role="status">
      Asseta manages this account under mandate <strong>{mandate.reference}</strong> (consent{' '}
      {mandate.consent_reference}).{' '}
      <Link component={RouterLink} to={ROUTES.tenantManagedService}>
        Review or revoke
      </Link>
    </Alert>
  );
}
