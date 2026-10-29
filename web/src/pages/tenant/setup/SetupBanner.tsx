import RocketLaunch from '@mui/icons-material/RocketLaunch';
import { Alert, AlertTitle, Button } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { ROUTES } from '../../../navigation/routes';
import { useSession } from '../../../session/useSession';

/**
 * Dashboard banner while the company is not yet set up for go-live. Its figures come from /me
 * (`setup_*`, null without `tenant.setup.read`), so it costs no extra request; hidden once the
 * checklist is complete or the owner hid it.
 */
export function SetupBanner() {
  const { activeTenant, hasPermission } = useSession();
  if (activeTenant === null || !hasPermission(PERMISSIONS.tenantSetupRead)) return null;
  const {
    setup_complete: complete,
    setup_dismissed: dismissed,
    setup_steps_done: done,
    setup_steps_total: total,
  } = activeTenant;
  if (complete !== false || dismissed === true) return null;
  const progress =
    done != null && total != null ? ` — ${String(done)} of ${String(total)} done` : '';
  return (
    <Alert
      severity="info"
      icon={<RocketLaunch />}
      action={
        <Button component={RouterLink} to={ROUTES.tenantSetup} color="inherit" size="small">
          Continue setup
        </Button>
      }
    >
      <AlertTitle>Get ready to go live{progress}</AlertTitle>A few setup steps help the team start
      working in Asseta with confidence.
    </Alert>
  );
}
