import { Alert, Button } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import { adjustmentRequestPath } from '../../../navigation/adjustmentRoutes';

/** A purchase with nothing to pay waits for a second person before its hours activate. */
export function PendingZeroAmountNotice({ requestId }: { requestId: string | null | undefined }) {
  if (requestId == null) return null;
  return (
    <Alert
      severity="warning"
      action={
        <Button component={RouterLink} to={adjustmentRequestPath(requestId)} size="small">
          Open the request
        </Button>
      }
    >
      This purchase has nothing to pay, so its hours stay inactive until someone else approves them.
    </Alert>
  );
}
