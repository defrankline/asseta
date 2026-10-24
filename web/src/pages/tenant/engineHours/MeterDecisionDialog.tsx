import { Alert, Button, Tooltip } from '@mui/material';
import type { ReactNode } from 'react';
import { mixed, object, string, type ObjectSchema } from 'yup';
import type { MeterDecisionIn } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useSession } from '../../../session/useSession';
import { withErrorCode } from '../shared/errorHints';
import { ENGINE_HOURS_ERROR_HINTS, OWN_PROPOSAL_TEXT } from './engineHoursDisplay';

type Decision = MeterDecisionIn['decision'];

interface DecisionValues {
  decision: Decision | '';
  note: string;
}

/** The server needs a note (5–2000 characters) on every engine-hour decision. */
export const DECISION_NOTE_MIN = 5;

const DECISION_OPTIONS = [
  { value: 'APPROVE', label: 'Approve' },
  { value: 'REJECT', label: 'Reject' },
];

const schema: ObjectSchema<DecisionValues> = object({
  decision: mixed<Decision | ''>()
    .oneOf(['APPROVE', 'REJECT'], 'Choose a decision')
    .required('Choose a decision'),
  note: string()
    .trim()
    .required('A note is required')
    .min(DECISION_NOTE_MIN, `At least ${String(DECISION_NOTE_MIN)} characters`)
    .max(2000, 'At most 2000 characters'),
});

interface MeterDecisionDialogProps<T> {
  title: string;
  summary: ReactNode;
  /** What approving / rejecting means, in plain language. */
  explanation: ReactNode;
  onDecide: (body: MeterDecisionIn, idempotencyKey: string) => Promise<T>;
  onDone: (result: T) => void;
  onClose: () => void;
}

/** Approve or reject an engine-hour proposal (baseline, classification, correction). Mount while open. */
export function MeterDecisionDialog<T>({
  title,
  summary,
  explanation,
  onDecide,
  onDone,
  onClose,
}: MeterDecisionDialogProps<T>) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<DecisionValues>
      open
      title={title}
      initialValues={{ decision: '', note: '' }}
      validationSchema={schema}
      submitLabel="Record decision"
      onClose={onClose}
      onSubmit={async (v) => {
        const body: MeterDecisionIn = {
          decision: v.decision === 'APPROVE' ? 'APPROVE' : 'REJECT',
          note: v.note.trim(),
        };
        try {
          onDone(await onDecide(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, ENGINE_HOURS_ERROR_HINTS);
        }
      }}
    >
      {summary}
      <Alert severity="info">{explanation}</Alert>
      <FormikSelectField name="decision" label="Decision" options={DECISION_OPTIONS} required />
      <FormikTextField
        name="note"
        label="Note"
        required
        multiline
        minRows={2}
        helperText="Kept on the record for audit (at least 5 characters)."
      />
    </FormDialog>
  );
}

interface DecideButtonProps {
  /** Who proposed the record; the proposer can never decide it. */
  proposedBy: string | null;
  label?: string;
  onClick: () => void;
}

/** "Decide" action, disabled with an explanation on the caller's own proposal. */
export function DecideButton({ proposedBy, label = 'Decide', onClick }: DecideButtonProps) {
  const { me } = useSession();
  const own = me !== null && proposedBy === me.user_id;
  if (own) {
    return (
      <Tooltip title={OWN_PROPOSAL_TEXT}>
        <span>
          <Button size="small" disabled aria-label={`${label} (${OWN_PROPOSAL_TEXT})`}>
            {label}
          </Button>
        </span>
      </Tooltip>
    );
  }
  return (
    <Button
      size="small"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      {label}
    </Button>
  );
}
