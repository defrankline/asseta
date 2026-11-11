import { Alert, Typography } from '@mui/material';
import { useState, type ReactNode } from 'react';
import { newUuid } from '../../../../api/ids';
import type { PettyCashAdvanceDto, PettyCashFundDto } from '../../../../api/pettyCashTypes';
import { pettyCashService } from '../../../../api/services/pettyCashService';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { FormDialog } from '../../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import {
  formatEnteredMoney,
  formatMoney,
  isDecimalString,
  signOfDecimal,
  sumDecimals,
} from '../../../../utils/money';
import { FormikStaffIdPicker } from '../../shared/financePickers';
import { FormikCashReasonIdPicker } from '../cash/custodyPickers';
import {
  ADJUSTMENT_DIRECTION_OPTIONS,
  adjustmentSchema,
  advanceSchema,
  amountNoteSchema,
  answerSchema,
  countSchema,
  ANSWER_CHOICES,
  holderChangeSchema,
  toAdjustmentPayload,
  toAdvancePayload,
  toCountPayload,
  toHolderChangePayload,
  type AdjustmentValues,
  type AdvanceValues,
  type AmountNoteValues,
  type AnswerValues,
  type CountValues,
  type HolderChangeValues,
} from './pettyCashForms';
import { FormikPersonIdPicker, FormikPettyEvidenceField } from './pettyCashPickers';
import { usePettyCashPolicy } from './pettyCashState';
import { decimal, fundSummary, hinted } from './dialogHelpers';

// --- count ----------------------------------------------------------------------------------------
function Difference({
  counted,
  expected,
  currency,
}: {
  counted: string;
  expected: string;
  currency: string;
}) {
  const c = counted.trim();
  if (!isDecimalString(c)) return null;
  const diff = sumDecimals([c, expected.startsWith('-') ? expected.slice(1) : `-${expected}`]);
  return (
    <Typography variant="body2" color="text.secondary">
      Difference against the cash expected: {formatMoney(diff, currency)}
      {signOfDecimal(diff) === 0 ? ' (none)' : ' (a variance is opened for follow-up)'}
    </Typography>
  );
}

export function CountDialog({
  fund,
  onDone,
  onClose,
}: {
  fund: PettyCashFundDto;
  onDone: (c: Awaited<ReturnType<typeof pettyCashService.recordCount>>) => void;
  onClose: () => void;
}) {
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(() => newUuid());
  const policy = usePettyCashPolicy();
  const expected = fund.balance?.available_to_spend;
  return (
    <FormDialog<CountValues>
      open
      title={`Count ${fund.name}`}
      initialValues={{ counted_amount: '', witness_user_id: '', evidence: [], note: '' }}
      validationSchema={countSchema}
      submitLabel="Record count"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = toCountPayload(v, fund.id, clientId);
        try {
          onDone(await pettyCashService.recordCount(body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      {(f) => (
        <>
          {fundSummary(fund, fund.balance)}
          <Alert severity="info">
            Count the cash in the box. It is compared with the cash expected now (available to
            spend); a difference opens a variance.
          </Alert>
          <FormikTextField
            name="counted_amount"
            label={`Amount counted (${fund.currency})`}
            required
            slotProps={decimal}
          />
          {expected !== undefined && (
            <Difference
              counted={f.values.counted_amount}
              expected={expected}
              currency={fund.currency}
            />
          )}
          <FormikPersonIdPicker
            name="witness_user_id"
            label={policy?.countWitnessRequired === true ? 'Witness' : 'Witness (optional)'}
            helperText={
              policy?.countWitnessRequired === true
                ? 'Your company asks for a witness; a count by the holder alone is marked as a self-count.'
                : 'Someone else who holds the count permission.'
            }
          />
          <FormikPettyEvidenceField />
          <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
        </>
      )}
    </FormDialog>
  );
}

// --- holder change --------------------------------------------------------------------------------
export function HolderChangeDialog({
  fund,
  onDone,
  onClose,
}: {
  fund: PettyCashFundDto;
  onDone: () => void;
  onClose: () => void;
}) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<HolderChangeValues>
      open
      title={`Change the holder of ${fund.name}`}
      initialValues={{
        to_staff_id: '',
        counted_amount: '',
        witness_user_id: '',
        evidence: [],
        note: '',
      }}
      validationSchema={holderChangeSchema}
      submitLabel="Start holder change"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = toHolderChangePayload(v);
        try {
          await pettyCashService.startHolderChange(fund.id, body, keyFor(body));
          onDone();
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      {fundSummary(fund, fund.balance)}
      <Alert severity="info">
        The cash is counted at the change. {fund.holder_staff_name ?? 'The current holder'} stays
        accountable until the new holder accepts the fund.
      </Alert>
      <FormikStaffIdPicker name="to_staff_id" label="New holder" required />
      <FormikTextField
        name="counted_amount"
        label={`Amount counted (${fund.currency})`}
        required
        slotProps={decimal}
      />
      <FormikPersonIdPicker name="witness_user_id" label="Witness (optional)" />
      <FormikPettyEvidenceField />
      <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
    </FormDialog>
  );
}

/** A yes / no answer with a note (holder change accept / decline, cancel). */
export function AnswerDialog<T>({
  title,
  summary,
  choice = 'holderChange',
  onAnswer,
  onDone,
  onClose,
}: {
  title: string;
  summary: ReactNode;
  choice?: keyof typeof ANSWER_CHOICES;
  onAnswer: (yes: boolean, note: string | null, key: string) => Promise<T>;
  onDone: (r: T) => void;
  onClose: () => void;
}) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<AnswerValues>
      open
      title={title}
      initialValues={{ answer: '', note: '' }}
      validationSchema={answerSchema}
      submitLabel="Record answer"
      onClose={onClose}
      onSubmit={async (v) => {
        const yes = v.answer === 'YES';
        const note = v.note.trim() === '' ? null : v.note.trim();
        try {
          onDone(await onAnswer(yes, note, keyFor({ yes, note })));
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      {summary}
      <FormikSelectField name="answer" label="Answer" options={ANSWER_CHOICES[choice]} required />
      <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
    </FormDialog>
  );
}

// --- adjustment -----------------------------------------------------------------------------------
export function AdjustmentDialog({
  fund,
  evidenceRequired = false,
  onDone,
  onClose,
}: {
  fund: PettyCashFundDto;
  evidenceRequired?: boolean;
  onDone: () => void;
  onClose: () => void;
}) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<AdjustmentValues>
      open
      title={`Propose an adjustment to ${fund.name}`}
      initialValues={{ direction: 'LOWER', amount: '', reason_id: '', reason: '', evidence: [] }}
      validationSchema={adjustmentSchema(evidenceRequired)}
      submitLabel="Propose"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = toAdjustmentPayload(v, fund.id);
        try {
          await pettyCashService.proposeAdjustment(body, keyFor(body));
          onDone();
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      {(f) => (
        <>
          {fundSummary(fund, fund.balance)}
          <Alert severity="info">
            A correction of the fund balance. It counts once someone other than you (and not the
            holder) approves it.
          </Alert>
          <FormikSelectField
            name="direction"
            label="Direction"
            options={ADJUSTMENT_DIRECTION_OPTIONS}
            required
          />
          <FormikTextField
            name="amount"
            label={`Amount (${fund.currency})`}
            required
            slotProps={decimal}
          />
          {isDecimalString(f.values.amount.trim()) && (
            <Typography variant="body2" color="text.secondary">
              The balance {f.values.direction === 'LOWER' ? 'goes down' : 'goes up'} by{' '}
              {formatEnteredMoney(f.values.amount, fund.currency)}.
            </Typography>
          )}
          <FormikCashReasonIdPicker
            kind="ADJUSTMENT"
            name="reason_id"
            label="Reason from your list (optional)"
            onOptionChange={(r) => {
              if (r !== null && f.values.reason.trim() === '')
                void f.setFieldValue('reason', r.label);
            }}
          />
          <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
          <FormikPettyEvidenceField required={evidenceRequired} />
        </>
      )}
    </FormDialog>
  );
}

// --- advances -------------------------------------------------------------------------------------
export function AdvanceDialog({
  fund,
  clearWithinDays,
  onDone,
  onClose,
}: {
  fund: PettyCashFundDto;
  clearWithinDays: number;
  onDone: (a: PettyCashAdvanceDto) => void;
  onClose: () => void;
}) {
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(() => newUuid());
  return (
    <FormDialog<AdvanceValues>
      open
      title={`Pay an advance from ${fund.name}`}
      initialValues={{ recipient_staff_id: '', amount: '', purpose: '' }}
      validationSchema={advanceSchema}
      submitLabel="Pay advance"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = toAdvancePayload(v, fund.id, clientId);
        try {
          onDone(await pettyCashService.issueAdvance(body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      {fundSummary(fund, fund.balance)}
      <Alert severity="info">
        Cash given before a purchase. The person records the expenses against this advance and hands
        back the change within {String(clearWithinDays)} days.
      </Alert>
      <FormikStaffIdPicker name="recipient_staff_id" label="Paid to" required />
      <FormikTextField
        name="amount"
        label={`Amount (${fund.currency})`}
        required
        slotProps={decimal}
      />
      <FormikTextField name="purpose" label="What it is for" required multiline minRows={2} />
    </FormDialog>
  );
}

export function ClearAdvanceDialog({
  advance: a,
  onDone,
  onClose,
}: {
  advance: PettyCashAdvanceDto;
  onDone: (a: PettyCashAdvanceDto) => void;
  onClose: () => void;
}) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<AmountNoteValues>
      open
      title={`Clear advance ${a.number}`}
      initialValues={{ amount: a.remaining, note: '' }}
      validationSchema={amountNoteSchema('Change handed back')}
      submitLabel="Clear advance"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = {
          change_returned: v.amount.trim(),
          note: v.note.trim() === '' ? null : v.note.trim(),
        };
        try {
          onDone(await pettyCashService.clearAdvance(a.id, body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Paid to', value: a.recipient_staff_name ?? '—' },
          { label: 'Advance', value: <MoneyText amount={a.amount} currency={a.currency} /> },
          {
            label: 'Approved spending',
            value: <MoneyText amount={a.approved_spending} currency={a.currency} />,
          },
          {
            label: 'Change expected',
            value: <MoneyText amount={a.remaining} currency={a.currency} strong />,
          },
        ]}
      />
      <Alert severity="info">
        Count the change handed back. A difference from the change expected opens a variance.
      </Alert>
      <FormikTextField name="amount" label="Change handed back" required slotProps={decimal} />
      <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
    </FormDialog>
  );
}
