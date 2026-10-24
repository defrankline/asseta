import { Alert, AlertTitle, Typography } from '@mui/material';
import type { JobDto } from '../../../api/types';
import { isFieldRequest, PENDING_PRICE } from '../shared/jobDisplay';

/** Who asked for a field-requested job and what the customer wanted; nothing for office jobs. */
export function FieldRequestInfo({ job }: { job: JobDto }) {
  if (!isFieldRequest(job)) return null;
  const who = job.requested_by_name ?? 'a supervisor';
  const note = job.request_note ?? null;
  return (
    <Alert severity="info">
      <AlertTitle>{`Requested from the field by ${who}`}</AlertTitle>
      {note !== null && note.trim() !== '' && (
        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
          {note}
        </Typography>
      )}
      {job.rate_source === PENDING_PRICE && job.status === 'PENDING_APPROVAL' && (
        <Typography variant="body2">
          No rate card applies to this machine; enter the hourly rate when approving.
        </Typography>
      )}
    </Alert>
  );
}
