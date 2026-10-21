import { Alert, Button } from '@mui/material';
import { STALE_RECORD_MESSAGE } from './LifecycleActionDialog';

interface StaleVersionAlertProps {
  /** Reload the record (and close the form). */
  onReload: () => void;
}

/** Shown in an edit form after the server answered STALE_VERSION; nothing was overwritten. */
export function StaleVersionAlert({ onReload }: StaleVersionAlertProps) {
  return (
    <Alert
      severity="warning"
      action={
        <Button color="inherit" size="small" onClick={onReload}>
          Reload
        </Button>
      }
    >
      {STALE_RECORD_MESSAGE}
    </Alert>
  );
}
