import { Alert, Link } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../access/permissionCodes';
import { ROUTES } from '../navigation/routes';
import { useSession } from '../session/useSession';

/**
 * Explains restricted tenant access (set by platform billing/entitlements, or by a requested company
 * closure). The server's `access_state_reason` is shown when it gives one.
 */
export function TenantAccessBanner() {
  const { mode, activeTenant, hasPermission } = useSession();
  if (mode.kind !== 'tenant' || activeTenant === null) return null;
  // The page adds its own full stop.
  const reason = (activeTenant.access_state_reason ?? '').trim().replace(/\.+$/, '');
  const closureLink =
    reason !== '' && hasPermission(PERMISSIONS.tenantCompanyClose) ? (
      <>
        {' '}
        <Link component={RouterLink} to={ROUTES.tenantCompanyClose} color="inherit">
          See Close company
        </Link>
        .
      </>
    ) : null;
  if (activeTenant.access_state === 'READ_ONLY') {
    return (
      <Alert severity="warning" className="mb-4" role="status">
        <strong>{activeTenant.name} is read-only.</strong>{' '}
        {reason !== '' ? (
          <>
            {reason}. You can view data and take a data export; other changes are disabled.
            {closureLink}
          </>
        ) : (
          <>
            You can view data and take a data export, but other changes are disabled until the
            subscription is restored. Contact your account owner.
          </>
        )}
      </Alert>
    );
  }
  if (activeTenant.access_state === 'BLOCKED') {
    return (
      <Alert severity="error" className="mb-4" role="alert">
        <strong>Access to {activeTenant.name} is blocked.</strong>{' '}
        {reason !== '' ? `${reason}. ` : ''}Tenant features are unavailable. Contact your account
        owner or Asseta support.
      </Alert>
    );
  }
  if (reason !== '') {
    return (
      <Alert severity="info" className="mb-4" role="status">
        {reason}.{closureLink}
      </Alert>
    );
  }
  return null;
}
