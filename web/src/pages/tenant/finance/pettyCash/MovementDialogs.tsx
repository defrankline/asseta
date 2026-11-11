import { Alert } from '@mui/material';
import { useCallback, useState } from 'react';
import { newUuid } from '../../../../api/ids';
import type { PettyCashFundDto, PettyCashMovementDto } from '../../../../api/pettyCashTypes';
import { pettyCashService } from '../../../../api/services/pettyCashService';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { FormDialog } from '../../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { signOfDecimal } from '../../../../utils/money';
import {
  ACK_ANSWER_OPTIONS,
  ackSchema,
  above,
  amountNoteSchema,
  fundingSchema,
  issueSchema,
  returnSchema,
  toAckPayload,
  toFundingPayload,
  toIssuePayload,
  toReturnPayload,
  toTopUpRequest,
  type AckValues,
  type AmountNoteValues,
  type FundingValues,
  type IssueValues,
  type ReturnValues,
} from './pettyCashForms';
import { FormikPettyEvidenceField } from './pettyCashPickers';
import { fundLabel, usePettyCashPolicy } from './pettyCashState';
import { AccountFields } from './dialogParts';
import { decimal, fundSummary, hinted } from './dialogHelpers';

// --- funding, top-up proposal and the holder's top-up request -----------------------------------
interface FundingDialogProps {
  fund: PettyCashFundDto;
  /** `propose`: the office proposes a funding or top-up; `request`: the holder asks for a top-up. */
  mode: 'propose' | 'request';
  onDone: (m: PettyCashMovementDto) => void;
  onClose: () => void;
}

/** Imprest top-up pre-filled with approved spending since the last top-up, capped at the limit. */
export function FundingDialog({ fund, mode, onDone, onClose }: FundingDialogProps) {
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(() => newUuid());
  const load = useCallback(
    (signal: AbortSignal) => pettyCashService.topUpSuggestion(fund.id, signal),
    [fund.id],
  );
  const res = useAsyncResource(load, []);
  const request = mode === 'request';
  return (
    <AsyncContent
      resource={res}
      loadingLabel="Working out the top-up"
      errorTitle="Could not work out the top-up"
    >
      {(s) => (
        <FormDialog<FundingValues>
          open
          title={request ? `Request a top-up of ${fund.name}` : `Propose money for ${fund.name}`}
          initialValues={{
            kind: 'TOP_UP',
            amount: signOfDecimal(s.suggested) > 0 ? s.suggested : '',
            cap: s.cap,
            above_cap_reason: '',
            deposit_account_id: '',
            method: '',
            reference: '',
            note: '',
          }}
          validationSchema={fundingSchema}
          submitLabel={request ? 'Send request' : 'Propose'}
          onClose={onClose}
          onSubmit={async (v) => {
            try {
              if (request) {
                const body = toTopUpRequest(v, clientId);
                onDone(await pettyCashService.requestTopUp(fund.id, body, keyFor(body)));
              } else {
                const body = toFundingPayload(v, fund.id, clientId);
                onDone(await pettyCashService.proposeFunding(body, keyFor(body)));
              }
            } catch (err) {
              throw hinted(err);
            }
          }}
        >
          {(f) => (
            <>
              <KeyValueGrid
                columns={2}
                items={[
                  { label: 'Fund', value: fundLabel(fund) },
                  {
                    label: 'Balance',
                    value: <MoneyText amount={s.balance} currency={s.currency} />,
                  },
                  {
                    label: 'Approved limit',
                    value: <MoneyText amount={s.approved_limit} currency={s.currency} />,
                  },
                  {
                    label: 'Already on its way',
                    value: <MoneyText amount={s.in_flight} currency={s.currency} />,
                  },
                  {
                    label: `Approved spending since the last top-up (${String(s.expenses.length)})`,
                    value: <MoneyText amount={s.spending_since} currency={s.currency} />,
                  },
                  {
                    label: 'Most that brings it to its limit',
                    value: <MoneyText amount={s.cap} currency={s.currency} strong />,
                  },
                ]}
              />
              <Alert severity="info">
                {request
                  ? 'Someone else approves and hands over the money; you then confirm what you received.'
                  : 'Someone other than you approves it; it is handed over afterwards and the holder confirms what they received.'}
              </Alert>
              {!request && (
                <FormikSelectField
                  name="kind"
                  label="Kind"
                  options={FUNDING_KIND_SELECT}
                  required
                />
              )}
              <FormikTextField
                name="amount"
                label={`Amount (${fund.currency})`}
                required
                slotProps={decimal}
              />
              {above(f.values.amount, s.cap) && (
                <FormikTextField
                  name="above_cap_reason"
                  label="Why more than the limit allows"
                  required
                  multiline
                  minRows={2}
                />
              )}
              {!request && (
                <AccountFields
                  currency={fund.currency}
                  accountLabel="From company account (optional)"
                />
              )}
              <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
            </>
          )}
        </FormDialog>
      )}
    </AsyncContent>
  );
}

const FUNDING_KIND_SELECT = [
  { value: 'TOP_UP', label: 'Top-up (refill what was spent)' },
  { value: 'FUNDING', label: 'Funding (first money or a larger amount)' },
] as const;

// --- hand over approved money -------------------------------------------------------------------
export function IssueDialog({
  movement: m,
  onDone,
  onClose,
}: {
  movement: PettyCashMovementDto;
  onDone: (m: PettyCashMovementDto) => void;
  onClose: () => void;
}) {
  const keyFor = useIdempotencyKey();
  const policy = usePettyCashPolicy();
  const required =
    (policy?.fundingEvidenceRequired ?? false) && m.evidence_attachment_ids.length === 0;
  return (
    <FormDialog<IssueValues>
      open
      title={`Hand over ${m.number}`}
      initialValues={{
        deposit_account_id: m.deposit_account_id ?? '',
        method: (m.method ?? '') as IssueValues['method'],
        reference: m.reference ?? '',
        evidence: [],
        note: '',
      }}
      validationSchema={issueSchema(required)}
      submitLabel="Record hand-over"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = toIssuePayload(v);
        try {
          onDone(await pettyCashService.issue(m.id, body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Fund', value: m.petty_cash_fund_name ?? '—' },
          { label: 'Holder', value: m.holder_staff_name ?? '—' },
          { label: 'Amount', value: <MoneyText amount={m.amount} currency={m.currency} strong /> },
        ]}
      />
      <Alert severity="info">
        The money counts in the fund once the holder confirms what they received.
      </Alert>
      <AccountFields currency={m.currency} accountLabel="From company account (optional)" />
      <FormikPettyEvidenceField required={required} />
      <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
    </FormDialog>
  );
}

// --- the holder answers money received ----------------------------------------------------------
export function AcknowledgeMovementDialog({
  movement: m,
  onDone,
  onClose,
}: {
  movement: PettyCashMovementDto;
  onDone: (m: PettyCashMovementDto) => void;
  onClose: () => void;
}) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<AckValues>
      open
      title={`Money received: ${m.number}`}
      initialValues={{ answer: '', amount_received: m.amount, note: '' }}
      validationSchema={ackSchema}
      submitLabel="Record answer"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = toAckPayload(v);
        try {
          onDone(await pettyCashService.acknowledge(m.id, body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      {(f) => (
        <>
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Fund', value: m.petty_cash_fund_name ?? '—' },
              {
                label: 'Amount handed over',
                value: <MoneyText amount={m.amount} currency={m.currency} strong />,
              },
              { label: 'Handed over by', value: m.issued_by_name ?? '—' },
              { label: 'Reference', value: m.reference ?? '—' },
            ]}
          />
          <Alert severity="info">
            Count the cash first. If the amount differs from what was handed over, a variance is
            opened for follow-up.
          </Alert>
          <FormikSelectField name="answer" label="Answer" options={ACK_ANSWER_OPTIONS} required />
          {f.values.answer === 'ACKNOWLEDGE' && (
            <FormikTextField
              name="amount_received"
              label="Amount you counted"
              required
              slotProps={decimal}
            />
          )}
          <FormikTextField
            name="note"
            label="Note"
            multiline
            minRows={2}
            helperText="Required when you did not receive it."
          />
        </>
      )}
    </FormDialog>
  );
}

// --- return (holder) and its confirmation (office) ----------------------------------------------
export function ReturnDialog({
  fund,
  onDone,
  onClose,
}: {
  fund: PettyCashFundDto;
  onDone: (m: PettyCashMovementDto) => void;
  onClose: () => void;
}) {
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(() => newUuid());
  const policy = usePettyCashPolicy();
  const required = policy?.returnEvidenceRequired ?? false;
  return (
    <FormDialog<ReturnValues>
      open
      title={`Return money from ${fund.name}`}
      initialValues={{
        amount: '',
        deposit_account_id: '',
        method: '',
        reference: '',
        evidence: [],
        note: '',
      }}
      validationSchema={returnSchema(required)}
      submitLabel="Record return"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = toReturnPayload(v, fund.id, clientId);
        try {
          onDone(await pettyCashService.claimReturn(body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      {fundSummary(fund, fund.balance)}
      <Alert severity="info">
        The fund balance goes down once the office confirms the amount it counted.
      </Alert>
      <FormikTextField
        name="amount"
        label={`Amount (${fund.currency})`}
        required
        slotProps={decimal}
      />
      <AccountFields currency={fund.currency} accountLabel="Into company account (optional)" />
      <FormikPettyEvidenceField required={required} />
      <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
    </FormDialog>
  );
}

export function ConfirmReturnDialog({
  movement: m,
  onDone,
  onClose,
}: {
  movement: PettyCashMovementDto;
  onDone: (m: PettyCashMovementDto) => void;
  onClose: () => void;
}) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<AmountNoteValues>
      open
      title={`Confirm return ${m.number}`}
      initialValues={{ amount: m.amount, note: '' }}
      validationSchema={amountNoteSchema('Amount counted')}
      submitLabel="Confirm"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = {
          amount_received: v.amount.trim(),
          note: v.note.trim() === '' ? null : v.note.trim(),
        };
        try {
          onDone(await pettyCashService.confirmReturn(m.id, body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Fund', value: m.petty_cash_fund_name ?? '—' },
          { label: 'Holder', value: m.holder_staff_name ?? '—' },
          {
            label: 'Amount returned',
            value: <MoneyText amount={m.amount} currency={m.currency} strong />,
          },
        ]}
      />
      <Alert severity="info">
        State what you counted. A difference opens a variance for follow-up.
      </Alert>
      <FormikTextField name="amount" label="Amount counted" required slotProps={decimal} />
      <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
    </FormDialog>
  );
}
