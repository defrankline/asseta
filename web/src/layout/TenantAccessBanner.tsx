import { Alert } from '@mui/material';
import { useSession } from '../session/useSession';

/** Explains restricted tenant access (set by platform billing/entitlements). */
export function TenantAccessBanner() {
  const { mode, activeTenant } = useSession();
  if (mode.kind !== 'tenant' || activeTenant === null) return null;
  if (activeTenant.access_state === 'READ_ONLY') {
    return (
      <Alert severity="warning" className="mb-4" role="status">
        <strong>{activeTenant.name} is read-only.</strong> You can view data, but changes are
        disabled until the subscription is restored. Contact your account owner.
      </Alert>
    );
  }
  if (activeTenant.access_state === 'BLOCKED') {
    return (
      <Alert severity="error" className="mb-4" role="alert">
        <strong>Access to {activeTenant.name} is blocked.</strong> Tenant features are unavailable.
        Contact your account owner or Asseta support.
      </Alert>
    );
  }
  return null;
}
