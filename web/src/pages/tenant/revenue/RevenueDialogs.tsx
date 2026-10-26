import { Alert } from '@mui/material';
import { mixed, object, string, type ObjectSchema } from 'yup';
import { withErrorCode } from '../../../api/lifecycle';
import { revenueService } from '../../../api/services/revenueService';
import type {
  NonRevenueActivityDto,
  NonRevenueApprovalDto,
  RevenueDecisionIn,
  RevenueDifferenceDto,
  RevenueReasonDto,
} from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../utils/time';
import { optionId } from '../shared/lookups';
import { PersonName } from '../shared/PersonName';
import {
  activityTypeLabel,
  differenceMachine,
  differencePeriod,
  NOTE_MIN,
  REVENUE_ERROR_HINTS,
} from './revenueDisplay';
import { resolveRevenueReason, revenueReasonLabel, searchRevenueReasons } from './revenueLookups';

const noteSchema = () =>
  string()
    .trim()
    .required('A note is required')
    .min(NOTE_MIN, `At least ${String(NOTE_MIN)} characters`)
    .max(2000, 'At most 2000 characters');

const NOTE_HELP = 'Kept on the record for audit (at least 5 characters).';

function DifferenceSummary({ d }: { d: RevenueDifferenceDto }) {
  return (
    <KeyValueGrid
      columns={2}
      items={[
        { label: 'Machine', value: differenceMachine(d) },
        { label: 'Period', value: differencePeriod(d) },
        {
          label: 'Expected revenue',
          value: <MoneyText amount={d.expected_amount} currency={d.currency} />,
        },
        {
          label: 'Money attributed',
          value: <MoneyText amount={d.attributed_amount} currency={d.currency} />,
        },
        {
          label: 'Difference to explain',
          value: <MoneyText amount={d.difference} currency={d.currency} strong />,
        },
        { label: 'Customer-work hours', value: `${d.customer_work_hours} h` },
      ]}
    />
  );
}

interface ReasonNoteValues {
  reason_id: string;
  note: string;
}

const reasonNoteSchema: ObjectSchema<ReasonNoteValues> = object({
  reason_id: string().required('Choose a reason'),
  note: noteSchema(),
});

function ReasonField() {
  return (
    <FormikAsyncIdAutocomplete<RevenueReasonDto>
      name="reason_id"
      label="Reason"
      fetchOptions={searchRevenueReasons}
      resolveOption={resolveRevenueReason}
      getOptionId={optionId}
      getOptionLabel={revenueReasonLabel}
      required
      noOptionsText="No active reasons; add them under Revenue reasons"
    />
  );
}

interface DialogProps<T> {
  onClose: () => void;
  onDone: (result: T) => void;
}

/** Propose an explanation of a revenue difference (a second person decides it). Mount while open. */
export function ExplainDifferenceDialog({
  difference: d,
  onClose,
  onDone,
}: DialogProps<RevenueDifferenceDto> & { difference: RevenueDifferenceDto }) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<ReasonNoteValues>
      open
      title={`Explain difference · ${differenceMachine(d)}`}
      initialValues={{ reason_id: '', note: '' }}
      validationSchema={reasonNoteSchema}
      submitLabel="Propose explanation"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = { reason_id: v.reason_id, note: v.note.trim() };
        try {
          onDone(await revenueService.explainDifference(d.id, body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, REVENUE_ERROR_HINTS);
        }
      }}
    >
      <DifferenceSummary d={d} />
      <Alert severity="info">
        Engine hours that did not turn into money are a difference to explain, not a finding against
        anyone. Your explanation is decided by someone else.
      </Alert>
      <ReasonField />
      <FormikTextField
        name="note"
        label="What happened"
        required
        multiline
        minRows={2}
        helperText={NOTE_HELP}
      />
    </FormDialog>
  );
}

type Decision = RevenueDecisionIn['decision'];

interface DecisionValues {
  decision: Decision | '';
  note: string;
}

const DIFFERENCE_DECISIONS: readonly { value: Decision; label: string }[] = [
  { value: 'APPROVE', label: 'Approve the explanation' },
  { value: 'REJECT', label: 'Reject the explanation (back to open)' },
  { value: 'CONFIRM', label: 'Confirm the difference (money to recover)' },
];

const CONFIRM_ONLY = DIFFERENCE_DECISIONS.filter((o) => o.value === 'CONFIRM');

const NON_REVENUE_DECISIONS = [
  { value: 'APPROVE', label: 'Approve as non-revenue' },
  { value: 'REJECT', label: 'Reject (keep as revenue)' },
];

const differenceDecisionSchema: ObjectSchema<DecisionValues> = object({
  decision: mixed<Decision | ''>()
    .oneOf(['APPROVE', 'REJECT', 'CONFIRM'], 'Choose a decision')
    .required('Choose a decision'),
  note: noteSchema(),
});

/** Decide a revenue difference: approve / reject a proposed explanation, or confirm it as real. */
export function DecideDifferenceDialog({
  difference: d,
  timeZone,
  onClose,
  onDone,
}: DialogProps<RevenueDifferenceDto> & { difference: RevenueDifferenceDto; timeZone: string }) {
  const keyFor = useIdempotencyKey();
  const proposed = d.status === 'EXPLANATION_PROPOSED';
  return (
    <FormDialog<DecisionValues>
      open
      title={`Decide difference · ${differenceMachine(d)}`}
      initialValues={{ decision: proposed ? '' : 'CONFIRM', note: '' }}
      validationSchema={differenceDecisionSchema}
      submitLabel="Record decision"
      onClose={onClose}
      onSubmit={async (v) => {
        const decision: Decision =
          v.decision === 'APPROVE' ? 'APPROVE' : v.decision === 'REJECT' ? 'REJECT' : 'CONFIRM';
        const body: RevenueDecisionIn = { decision, note: v.note.trim() };
        try {
          onDone(await revenueService.decideDifference(d.id, body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, REVENUE_ERROR_HINTS);
        }
      }}
    >
      <DifferenceSummary d={d} />
      {proposed && (
        <KeyValueGrid
          columns={2}
          items={[
            { label: 'Reason', value: d.reason_name ?? '—' },
            { label: 'What happened', value: d.explanation_note ?? '—' },
            {
              label: 'Explained by',
              value: <PersonName userId={d.explained_by} name={d.explained_by_name} />,
            },
            {
              label: 'Explained',
              value: d.explained_at === null ? '—' : formatInstantIn(d.explained_at, timeZone),
            },
          ]}
        />
      )}
      <Alert severity="info">
        Approving records the difference as explained. Rejecting sends it back to be explained
        again. Confirming records the difference as real money to recover.
      </Alert>
      {proposed ? (
        <FormikSelectField
          name="decision"
          label="Decision"
          options={DIFFERENCE_DECISIONS}
          required
        />
      ) : (
        <FormikSelectField name="decision" label="Decision" options={CONFIRM_ONLY} required />
      )}
      <FormikTextField
        name="note"
        label="Note"
        required
        multiline
        minRows={2}
        helperText={NOTE_HELP}
      />
    </FormDialog>
  );
}

const activityPeriod = (a: { started_at: string; ended_at: string }, timeZone: string): string =>
  `${formatInstantIn(a.started_at, timeZone)} → ${formatInstantIn(a.ended_at, timeZone)}`;

/** Explain non-revenue time inside a job (e.g. movement); a second person approves it. Mount while open. */
export function ExplainNonRevenueDialog({
  activity: a,
  timeZone,
  onClose,
  onDone,
}: DialogProps<NonRevenueApprovalDto> & { activity: NonRevenueActivityDto; timeZone: string }) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<ReasonNoteValues>
      open
      title={`Explain ${activityTypeLabel(a.activity_type).toLowerCase()} · ${a.hours} h`}
      initialValues={{ reason_id: '', note: a.note ?? '' }}
      validationSchema={reasonNoteSchema}
      submitLabel="Propose explanation"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = { activity_id: a.activity_id, reason_id: v.reason_id, note: v.note.trim() };
        try {
          onDone(await revenueService.proposeApproval(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, REVENUE_ERROR_HINTS);
        }
      }}
    >
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Machine', value: differenceMachine(a) },
          { label: 'Job', value: a.job_number ?? '—' },
          { label: 'Type', value: activityTypeLabel(a.activity_type) },
          { label: 'Hours', value: `${a.hours} h` },
          { label: 'When', value: activityPeriod(a, timeZone) },
        ]}
      />
      <Alert severity="info">
        Until someone else approves it, this time counts as customer work and expected revenue.
      </Alert>
      <ReasonField />
      <FormikTextField
        name="note"
        label="What happened"
        required
        multiline
        minRows={2}
        helperText={NOTE_HELP}
      />
    </FormDialog>
  );
}

interface ApproveValues {
  decision: 'APPROVE' | 'REJECT' | '';
  note: string;
}

const approveSchema: ObjectSchema<ApproveValues> = object({
  decision: mixed<'APPROVE' | 'REJECT' | ''>()
    .oneOf(['APPROVE', 'REJECT'], 'Choose a decision')
    .required('Choose a decision'),
  note: noteSchema(),
});

/** Approve or reject an explanation of non-revenue time (never one's own). Mount while open. */
export function DecideNonRevenueDialog({
  approval: a,
  timeZone,
  onClose,
  onDone,
}: DialogProps<NonRevenueApprovalDto> & { approval: NonRevenueApprovalDto; timeZone: string }) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<ApproveValues>
      open
      title={`Decide non-revenue time · ${a.hours} h · ${differenceMachine(a)}`}
      initialValues={{ decision: '', note: '' }}
      validationSchema={approveSchema}
      submitLabel="Record decision"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = {
          decision: v.decision === 'APPROVE' ? ('APPROVE' as const) : ('REJECT' as const),
          note: v.note.trim(),
        };
        try {
          onDone(await revenueService.decideApproval(a.id, body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, REVENUE_ERROR_HINTS);
        }
      }}
    >
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Job', value: a.job_number ?? '—' },
          { label: 'Type', value: activityTypeLabel(a.activity_type) },
          { label: 'Hours', value: `${a.hours} h` },
          { label: 'When', value: activityPeriod(a, timeZone) },
          { label: 'Reason', value: a.reason_name ?? '—' },
          { label: 'What happened', value: a.note },
          {
            label: 'Explained by',
            value: <PersonName userId={a.proposed_by} name={a.proposed_by_name} />,
          },
        ]}
      />
      <Alert severity="info">
        Approving removes this time from customer work and expected revenue. Rejecting keeps it as
        revenue; it can be explained again.
      </Alert>
      <FormikSelectField
        name="decision"
        label="Decision"
        options={NON_REVENUE_DECISIONS}
        required
      />
      <FormikTextField
        name="note"
        label="Note"
        required
        multiline
        minRows={2}
        helperText={NOTE_HELP}
      />
    </FormDialog>
  );
}
