import { Alert } from '@mui/material';
import type { ReactNode } from 'react';
import { useState } from 'react';
import { CAPABILITY, useCapabilityEnabled } from '../../../../access/capabilities';
import { newUuid } from '../../../../api/ids';
import { custodyService } from '../../../../api/services/custodyService';
import type { CashHandoverDto } from '../../../../api/types';
import type {
  CashAcknowledgementIn,
  CashTransferDto,
  CustodianDto,
} from '../../../../api/custodyTypes';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { FormDialog } from '../../../../components/forms/FormDialog';
import { FormikDateTimeField } from '../../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { StepperFormDialog } from '../../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { formatEnteredMoney } from '../../../../utils/money';
import { formatInstantIn } from '../../../../utils/time';
import { withErrorCode } from '../../shared/errorHints';
import { CURRENCY_OPTIONS } from '../../shared/financeDisplay';
import { CUSTODY_ERROR_HINTS } from './custodyDisplay';
import {
  ackSchema,
  remittanceDecisionSchema,
  toAckPayload,
  toRemittanceDecisionPayload,
  toTransferPayload,
  transferSchema,
  type AckValues,
  type RemittanceDecisionValues,
  type TransferValues,
} from './custodyForms';
import { type CashPolicy } from './custodyHooks';
import { FormikCustodianIdPicker } from './custodyPickers';

const hinted = (err: unknown) => withErrorCode(err, CUSTODY_ERROR_HINTS);
const entered = (amount: string, currency: string) => formatEnteredMoney(amount, currency);

// --- transfer ---------------------------------------------------------------------------------------------
interface TransferDialogProps {
  /** Field work without permission to record for others: the caller is the sender. */
  ownCustody: boolean;
  policy: CashPolicy | null;
  timeZone: string;
  onClose: () => void;
  onRecorded: (transfer: CashTransferDto) => void;
}

/** Field-to-field transfer: declared by the sender, acknowledged by the receiver. Never a company receipt. */
export function TransferDialog({
  ownCustody,
  policy,
  timeZone,
  onClose,
  onRecorded,
}: TransferDialogProps) {
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(newUuid);
  const [from, setFrom] = useState<CustodianDto | null>(null);
  const [to, setTo] = useState<CustodianDto | null>(null);
  const [initial] = useState<TransferValues>(() => ({
    from_staff_id: '',
    to_staff_id: '',
    amount: '',
    currency: '',
    transferred_at: new Date().toISOString(),
    note: '',
    amount_received: '',
  }));
  const receiverCounts = policy?.recorderReceiverCountsAsAck ?? true;
  return (
    <StepperFormDialog<TransferValues>
      open
      title="Record cash transfer"
      initialValues={initial}
      validationSchema={transferSchema}
      submitLabel="Record transfer"
      onClose={onClose}
      steps={[
        {
          label: 'Transfer',
          fields: ['from_staff_id', 'to_staff_id', 'amount', 'currency'],
          render: () => (
            <>
              {!ownCustody && (
                <FormikCustodianIdPicker
                  name="from_staff_id"
                  label="Handed over by (sender)"
                  helperText="Leave empty when you are the sender."
                  onOptionChange={setFrom}
                />
              )}
              <FormikCustodianIdPicker
                name="to_staff_id"
                label="Received by (receiver)"
                required
                onOptionChange={setTo}
              />
              <FormikTextField
                name="amount"
                label="Amount handed over"
                required
                slotProps={{ htmlInput: { inputMode: 'decimal' } }}
              />
              <FormikSelectField name="currency" label="Currency" options={CURRENCY_OPTIONS} />
            </>
          ),
        },
        {
          label: 'Details',
          fields: ['transferred_at', 'note', 'amount_received'],
          render: () => (
            <>
              <FormikDateTimeField
                name="transferred_at"
                label="Handed over at"
                timeZone={timeZone}
                required
              />
              <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
              {receiverCounts && (
                <FormikTextField
                  name="amount_received"
                  label="Amount actually received (optional)"
                  helperText="Only when you are the receiver: recording it is your acknowledgement."
                  slotProps={{ htmlInput: { inputMode: 'decimal' } }}
                />
              )}
            </>
          ),
        },
      ]}
      renderReview={(v) => (
        <>
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Sender', value: from?.full_name ?? 'Me' },
              { label: 'Receiver', value: to?.full_name ?? v.to_staff_id },
              { label: 'Amount', value: entered(v.amount, v.currency) },
              { label: 'Handed over at', value: formatInstantIn(v.transferred_at, timeZone) },
            ]}
          />
          <Alert severity="info">
            {policy?.transferAckRequired === false
              ? 'This tenant does not require the receiver to acknowledge transfers: it counts as received at the declared amount.'
              : 'The cash stays in the sender’s custody (in transit) until the receiver acknowledges the amount actually received.'}
          </Alert>
        </>
      )}
      onSubmit={async (v) => {
        const body = toTransferPayload(v, clientId);
        try {
          onRecorded(await custodyService.recordTransfer(body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    />
  );
}

// --- acknowledgement (transfer / float) -------------------------------------------------------------------
interface AcknowledgeDialogProps<T> {
  title: string;
  summary: ReactNode;
  declared: string;
  onAnswer: (body: CashAcknowledgementIn, idempotencyKey: string) => Promise<T>;
  onDone: (result: T) => void;
  onClose: () => void;
}

const ACK_OPTIONS = [
  { value: 'ACKNOWLEDGE', label: 'Acknowledge (cash received)' },
  { value: 'DISPUTE', label: 'Dispute (not received)' },
] as const;

/** The receiver states the amount actually received (a difference opens a variance) or disputes it. */
export function AcknowledgeDialog<T>({
  title,
  summary,
  declared,
  onAnswer,
  onDone,
  onClose,
}: AcknowledgeDialogProps<T>) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<AckValues>
      open
      title={title}
      initialValues={{ decision: '', amount_received: declared, note: '' }}
      validationSchema={ackSchema}
      submitLabel="Record answer"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = toAckPayload(v);
        try {
          onDone(await onAnswer(body, keyFor(body)));
        } catch (err) {
          throw hinted(err);
        }
      }}
    >
      {(f) => (
        <>
          {summary}
          <Alert severity="info">
            Count the cash first. If the amount received differs from the declared amount, a
            variance is opened for follow-up.
          </Alert>
          <FormikSelectField name="decision" label="Answer" options={ACK_OPTIONS} required />
          {f.values.decision === 'ACKNOWLEDGE' && (
            <FormikTextField
              name="amount_received"
              label="Amount actually received"
              required
              slotProps={{ htmlInput: { inputMode: 'decimal' } }}
            />
          )}
          <FormikTextField
            name="note"
            label="Note"
            multiline
            minRows={2}
            helperText="Required when disputing."
          />
        </>
      )}
    </FormDialog>
  );
}

// --- remittance decision ----------------------------------------------------------------------------------
const REMIT_OPTIONS = [
  { value: 'CONFIRM', label: 'Confirm (cash counted)' },
  { value: 'REJECT', label: 'Reject (not received)' },
] as const;

interface RemittanceDecisionDialogProps {
  handover: CashHandoverDto;
  custodianName: string;
  timeZone: string;
  onDone: (result: CashHandoverDto) => void;
  onClose: () => void;
}

/** The office confirms a remittance with the amount actually received (a difference opens a variance). */
export function RemittanceDecisionDialog({
  handover: h,
  custodianName,
  timeZone,
  onDone,
  onClose,
}: RemittanceDecisionDialogProps) {
  const keyFor = useIdempotencyKey();
  /** The amount received (and the variance it opens) is a cash custody control. */
  const withAmount = useCapabilityEnabled(CAPABILITY.cashCustody);
  return (
    <FormDialog<RemittanceDecisionValues>
      open
      title="Confirm remittance"
      initialValues={{ decision: '', amount_received: h.amount, note: '' }}
      validationSchema={remittanceDecisionSchema}
      submitLabel="Record decision"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = toRemittanceDecisionPayload(v, withAmount);
        try {
          onDone(await custodyService.decideRemittance(h.id, body, keyFor(body)));
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
              { label: 'Custodian', value: custodianName },
              {
                label: 'Amount declared',
                value: <MoneyText amount={h.amount} currency={h.currency} strong />,
              },
              { label: 'Handed over', value: formatInstantIn(h.handed_at, timeZone) },
              { label: 'Reference', value: h.reference ?? '—' },
            ]}
          />
          <Alert severity="info">
            {withAmount
              ? 'Confirm only after counting the cash or seeing the deposit. Enter the amount actually received; a difference from the declared amount opens a variance. A rejected remittance never reduces the custodian’s outstanding cash.'
              : 'Confirm only after counting the cash or seeing the deposit. A rejected remittance never reduces the custodian’s outstanding cash.'}
          </Alert>
          <FormikSelectField name="decision" label="Decision" options={REMIT_OPTIONS} required />
          {withAmount && f.values.decision === 'CONFIRM' && (
            <FormikTextField
              name="amount_received"
              label="Amount received"
              required
              slotProps={{ htmlInput: { inputMode: 'decimal' } }}
            />
          )}
          <FormikTextField
            name="note"
            label="Note / reason"
            multiline
            minRows={2}
            helperText="Required when rejecting; kept on the record for audit."
          />
        </>
      )}
    </FormDialog>
  );
}
