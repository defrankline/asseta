import { Alert, Button } from '@mui/material';
import { useNavigate } from 'react-router';
import { ROUTES } from '../navigation/routes';
import { mandateScopeLabel } from '../session/mandateDisplay';
import { useSession } from '../session/useSession';

/** Persistent notice while platform staff act for a client under a managed-service mandate. */
export function MandateBanner() {
  const { mode, activeTenant, setMode } = useSession();
  const navigate = useNavigate();
  const mandate = activeTenant?.mandate ?? null;
  if (mode.kind !== 'tenant' || activeTenant === null || mandate === null) return null;

  return (
    <Alert
      severity="warning"
      className="mb-4"
      role="status"
      action={
        <Button
          color="inherit"
          size="small"
          onClick={() => {
            void setMode({ kind: 'platform' }).then(() => navigate(ROUTES.home));
          }}
        >
          Return to your tenant
        </Button>
      }
    >
      Acting for <strong>{activeTenant.name}</strong> under managed-service mandate{' '}
      <strong>{mandate.reference}</strong> ({mandateScopeLabel(mandate.scope)}). Everything you do
      is recorded for the client.
    </Alert>
  );
}
