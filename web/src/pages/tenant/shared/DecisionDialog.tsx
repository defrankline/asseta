import { Alert } from '@mui/material';
import type { ReactNode } from 'react';
import { mixed, object, string, type ObjectSchema } from 'yup';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { withErrorCode } from './errorHints';
import { FINANCE_ERROR_HINTS } from './financeDisplay';

type Decision = 'APPROVE' | 'REJECT';
export type DecisionKind = 'verify' | 'approve';

/** Code-defined decision options per record type. */
const DECISION_OPTIONS: Readonly<
  Record<DecisionKind, readonly { value: Decision; label: string }[]>
> = {
  verify: [
    { value: 'APPROVE', label: 'Verify (money received)' },
    { value: 'REJECT', label: 'Reject (not received)' },
  ],
  approve: [
    { value: 'APPROVE', label: 'Approve' },
    { value: 'REJECT', label: 'Reject' },
  ],
};

interface DecisionValues {
  decision: Decision | '';
  note: string;
}

/** A rejection always needs a reason; an approval note is optional. */
export const NOTE_MIN = 3;
export const NOTE_MAX = 1000;

const schema: ObjectSchema<DecisionValues> = object({
  decision: mixed<Decision | ''>()
    .oneOf(['APPROVE', 'REJECT'], 'Choose a decision')
    .required('Choose a decision'),
  note: string()
    .trim()
    .ensure()
    .max(NOTE_MAX, `At most ${String(NOTE_MAX)} characters`)
    .when('decision', {
      is: 'REJECT',
      then: (s) =>
        s
          .required('A reason is required to reject')
          .min(NOTE_MIN, `At least ${String(NOTE_MIN)} characters`),
    }),
});

interface DecisionDialogProps<T> {
  title: string;
  /** What is being decided (amount, who, evidence). */
  summary: ReactNode;
  /** What each outcome means for balances / custody, in plain language. */
  explanation: ReactNode;
  /** `verify`: payments and handovers (Verify / Reject); `approve`: approval requests. */
  kind: DecisionKind;
  /** Throw (ideally an ApiError) to keep the dialog open with the server code. */
  onDecide: (approve: boolean, note: string | null, idempotencyKey: string) => Promise<T>;
  onDone: (result: T) => void;
  onClose: () => void;
}

/**
 * Verify / approve or reject a claimed record (payment, handover, expense approval). Segregation of
 * duties is enforced by the API (SEGREGATION_OF_DUTIES stays visible here); callers also hide this
 * for the recorder. Mount only while open.
 */
export function DecisionDialog<T>({
  title,
  summary,
  explanation,
  kind,
  onDecide,
  onDone,
  onClose,
}: DecisionDialogProps<T>) {
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
        const approve = v.decision === 'APPROVE';
        const note = v.note.trim() === '' ? null : v.note.trim();
        try {
          onDone(await onDecide(approve, note, keyFor({ approve, note })));
        } catch (err) {
          throw withErrorCode(err, FINANCE_ERROR_HINTS);
        }
      }}
    >
      {summary}
      <Alert severity="info">{explanation}</Alert>
      <FormikSelectField
        name="decision"
        label="Decision"
        options={DECISION_OPTIONS[kind]}
        required
      />
      <FormikTextField
        name="note"
        label="Note / reason"
        multiline
        minRows={2}
        helperText="Required when rejecting; kept on the record for audit."
      />
    </FormDialog>
  );
}
