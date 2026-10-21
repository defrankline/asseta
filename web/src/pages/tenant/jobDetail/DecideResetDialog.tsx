import { Alert, Typography } from '@mui/material';
import { mixed, object, string, type ObjectSchema } from 'yup';
import { meterService } from '../../../api/services/meterService';
import type { ResetDto, ReviewIn, ReviewOutcome } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../utils/time';
import { withErrorCode } from '../shared/errorHints';
import { RESET_ERROR_HINTS } from '../shared/jobDisplay';

/** decideMeterReset reuses the review outcome: EXPLAINED approves, CONFIRMED rejects. */
const OUTCOME_OPTIONS = [
  { value: 'EXPLAINED', label: 'Approve reset (documented reason accepted)' },
  { value: 'CONFIRMED', label: 'Reject reset' },
];

interface DecideValues {
  outcome: ReviewOutcome | '';
  note: string;
}

const schema: ObjectSchema<DecideValues> = object({
  outcome: mixed<ReviewOutcome | ''>()
    .oneOf(['EXPLAINED', 'CONFIRMED'], 'Choose a decision')
    .required('Choose a decision'),
  note: string()
    .trim()
    .required('A note is required')
    .min(5, 'At least 5 characters')
    .max(2000, 'At most 2000 characters'),
});

interface DecideResetDialogProps {
  /** A PENDING reset picked from the machine's reset list. */
  reset: ResetDto;
  timeZone: string;
  onClose: () => void;
  onDecided: (reset: ResetDto) => void;
}

/** Approver decision on a meter reset; the requester cannot decide their own (SEGREGATION_OF_DUTIES). */
export function DecideResetDialog({ reset, timeZone, onClose, onDecided }: DecideResetDialogProps) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<DecideValues>
      open
      title="Decide meter reset"
      initialValues={{ outcome: '', note: '' }}
      validationSchema={schema}
      submitLabel="Record decision"
      onClose={onClose}
      onSubmit={async (v) => {
        const body: ReviewIn = {
          outcome: v.outcome === '' ? 'CONFIRMED' : v.outcome,
          note: v.note.trim(),
        };
        const id = reset.id;
        try {
          onDecided(await meterService.decideReset(id, body, keyFor({ id, ...body })));
        } catch (err) {
          throw withErrorCode(err, RESET_ERROR_HINTS);
        }
      }}
    >
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Old reading', value: reset.old_reading },
          { label: 'New reading', value: reset.new_reading },
          { label: 'Effective time', value: formatInstantIn(reset.effective_at, timeZone) },
          { label: 'Reason', value: reset.reason },
        ]}
      />
      <Alert severity="info">
        <Typography variant="body2">
          Approving re-bases later readings for this machine from the effective time. The person who
          requested a reset cannot decide it.
        </Typography>
      </Alert>
      <FormikSelectField name="outcome" label="Decision" options={OUTCOME_OPTIONS} required />
      <FormikTextField name="note" label="Note" required multiline minRows={2} />
    </FormDialog>
  );
}
