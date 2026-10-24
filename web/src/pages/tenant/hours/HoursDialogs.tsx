import { Alert, Button, Tooltip } from '@mui/material';
import type { ReactNode } from 'react';
import { mixed, object, string, type ObjectSchema } from 'yup';
import type { ReasonKind } from '../../../api/hoursTypes';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { withErrorCode } from '../shared/errorHints';
import { HOURS_ERROR_HINTS, OWN_REQUEST_TEXT } from './hoursDisplay';
import { FormikReasonCodePicker } from './hoursPickers';

type Decision = 'APPROVE' | 'REJECT';

const DECISIONS: readonly { value: Decision; label: string }[] = [
  { value: 'APPROVE', label: 'Approve' },
  { value: 'REJECT', label: 'Reject' },
];

interface DecisionValues {
  decision: Decision | '';
  note: string;
}

const decisionSchema: ObjectSchema<DecisionValues> = object({
  decision: mixed<Decision | ''>()
    .oneOf(['APPROVE', 'REJECT'], 'Choose a decision')
    .required('Choose a decision'),
  note: string()
    .trim()
    .ensure()
    .max(1000, 'At most 1000 characters')
    .when('decision', {
      is: 'REJECT',
      then: (s) => s.required('A reason is required to reject').min(3, 'At least 3 characters'),
    }),
});

interface DecideDialogProps<T> {
  title: string;
  summary: ReactNode;
  /** What approving does, in plain language. */
  explanation: ReactNode;
  onDecide: (body: { approve: boolean; note: string | null }, key: string) => Promise<T>;
  onDone: (result: T) => void;
  onClose: () => void;
}

/** Approve / reject a proposal or request (the server refuses your own: SEGREGATION_OF_DUTIES). */
export function DecideDialog<T>({
  title,
  summary,
  explanation,
  onDecide,
  onDone,
  onClose,
}: DecideDialogProps<T>) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<DecisionValues>
      open
      title={title}
      initialValues={{ decision: '', note: '' }}
      validationSchema={decisionSchema}
      submitLabel="Record decision"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = {
          approve: v.decision === 'APPROVE',
          note: v.note.trim() === '' ? null : v.note.trim(),
        };
        try {
          onDone(await onDecide(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, HOURS_ERROR_HINTS);
        }
      }}
    >
      {summary}
      <Alert severity="info">{explanation}</Alert>
      <FormikSelectField name="decision" label="Decision" options={DECISIONS} required />
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

interface ReasonValues {
  reason: string;
  reason_code_id: string;
}

interface ReasonDialogProps<T> {
  title: string;
  submitLabel: string;
  summary?: ReactNode;
  /** Offer a reason from the tenant list of this kind (required when the policy says so). */
  reasonKind?: ReasonKind;
  reasonCodeRequired?: boolean;
  onSubmit: (body: { reason: string; reason_code_id: string | null }, key: string) => Promise<T>;
  onDone: (result: T) => void;
  onClose: () => void;
}

/** A free-text reason (3–1000 characters), optionally with a reason from the tenant list. */
export function ReasonDialog<T>({
  title,
  submitLabel,
  summary,
  reasonKind,
  reasonCodeRequired = false,
  onSubmit,
  onDone,
  onClose,
}: ReasonDialogProps<T>) {
  const keyFor = useIdempotencyKey();
  const schema: ObjectSchema<ReasonValues> = object({
    reason: string()
      .trim()
      .required('A reason is required')
      .min(3, 'At least 3 characters')
      .max(1000, 'At most 1000 characters'),
    reason_code_id: string()
      .ensure()
      .test(
        'required',
        'Choose a reason from the list',
        (v) => !reasonCodeRequired || reasonKind === undefined || v !== '',
      ),
  });
  return (
    <FormDialog<ReasonValues>
      open
      title={title}
      initialValues={{ reason: '', reason_code_id: '' }}
      validationSchema={schema}
      submitLabel={submitLabel}
      onClose={onClose}
      onSubmit={async (v) => {
        const body = {
          reason: v.reason.trim(),
          reason_code_id: v.reason_code_id === '' ? null : v.reason_code_id,
        };
        try {
          onDone(await onSubmit(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, HOURS_ERROR_HINTS);
        }
      }}
    >
      {summary}
      {reasonKind !== undefined && (
        <FormikReasonCodePicker
          name="reason_code_id"
          kind={reasonKind}
          label="Reason from your list"
          required={reasonCodeRequired}
        />
      )}
      <FormikTextField name="reason" label="Reason" multiline minRows={2} required />
    </FormDialog>
  );
}

/** "Decide" button: disabled with an explanation on your own proposal / request. */
export function DecideButton({
  own,
  label = 'Decide',
  onClick,
}: {
  own: boolean;
  label?: string;
  onClick: () => void;
}) {
  if (own) {
    return (
      <Tooltip title={OWN_REQUEST_TEXT}>
        <span>
          <Button size="small" disabled aria-label={`${label} (${OWN_REQUEST_TEXT})`}>
            {label}
          </Button>
        </span>
      </Tooltip>
    );
  }
  return (
    <Button size="small" onClick={onClick}>
      {label}
    </Button>
  );
}

/** Shown on hours screens when the tenant switched the capability off (history stays readable). */
export function HoursOffNotice({ off }: { off: boolean }) {
  if (!off) return null;
  return (
    <Alert severity="info">
      Customer hours are switched off in your company policy. Existing records stay readable; new
      purchases and requests are not possible.
    </Alert>
  );
}
