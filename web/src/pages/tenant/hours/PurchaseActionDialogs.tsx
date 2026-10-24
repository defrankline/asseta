import { Alert, Typography } from '@mui/material';
import { useState } from 'react';
import { object, string, type ObjectSchema } from 'yup';
import type { HoursPurchaseDto, TransferDto } from '../../../api/hoursTypes';
import { newUuid } from '../../../api/ids';
import { hoursRequestService, hoursService } from '../../../api/services/hoursService';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { positiveDecimalField } from '../../platform/shared/validators';
import { withErrorCode } from '../shared/errorHints';
import { FormikMachineIdPicker } from '../shared/financePickers';
import { orNull } from '../shared/formRules';
import { HOURS_ERROR_HINTS, hoursText } from './hoursDisplay';
import {
  FormikCustomerPaymentPicker,
  FormikPurchaseIdPicker,
  FormikReasonCodePicker,
} from './hoursPickers';

const decimal = { htmlInput: { inputMode: 'decimal' as const } };
const reasonField = () =>
  string()
    .trim()
    .required('A reason is required')
    .min(3, 'At least 3 characters')
    .max(1000, 'At most 1000 characters');

interface AllocateValues {
  payment_id: string;
  amount: string;
}

const allocateSchema: ObjectSchema<AllocateValues> = object({
  payment_id: string().required('Choose the payment'),
  amount: positiveDecimalField('Amount'),
});

/** Link (part of) a customer payment to this purchase; hours activate when the payment is verified. */
export function AllocatePaymentDialog({
  purchase,
  onClose,
  onDone,
}: {
  purchase: HoursPurchaseDto;
  onClose: () => void;
  onDone: (p: HoursPurchaseDto) => void;
}) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<AllocateValues>
      open
      title={`Allocate a payment to ${purchase.purchase_number}`}
      initialValues={{ payment_id: '', amount: purchase.totals.amount_outstanding }}
      validationSchema={allocateSchema}
      submitLabel="Allocate payment"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = { payment_id: v.payment_id, amount: v.amount.trim() };
        try {
          onDone(await hoursService.allocatePayment(purchase.id, body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, HOURS_ERROR_HINTS);
        }
      }}
    >
      <Typography variant="body2">
        Outstanding: {purchase.totals.amount_outstanding} {purchase.currency}
      </Typography>
      <FormikCustomerPaymentPicker
        name="payment_id"
        label="Customer payment"
        customerId={purchase.customer_id}
        required
      />
      <FormikTextField name="amount" label="Amount to allocate" required slotProps={decimal} />
      <Alert severity="info">
        Hours activate only once the payment is verified by someone other than the recorder.
      </Alert>
    </FormDialog>
  );
}

interface CreditValues {
  hours: string;
  reason: string;
}

const creditSchema: ObjectSchema<CreditValues> = object({
  hours: positiveDecimalField('Hours'),
  reason: reasonField(),
});

/** Activate hours awaiting payment against the customer's approved credit arrangement. */
export function ActivateOnCreditDialog({
  purchase,
  onClose,
  onDone,
}: {
  purchase: HoursPurchaseDto;
  onClose: () => void;
  onDone: (p: HoursPurchaseDto) => void;
}) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<CreditValues>
      open
      title={`Activate ${purchase.purchase_number} on credit`}
      initialValues={{ hours: purchase.totals.awaiting_activation, reason: '' }}
      validationSchema={creditSchema}
      submitLabel="Activate on credit"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = { hours: v.hours.trim(), reason: v.reason.trim() };
        try {
          onDone(await hoursService.activateOnCredit(purchase.id, body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, HOURS_ERROR_HINTS);
        }
      }}
    >
      <Typography variant="body2">
        Awaiting activation: {hoursText(purchase.totals.awaiting_activation)}
      </Typography>
      <FormikTextField name="hours" label="Hours to activate" required slotProps={decimal} />
      <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
      <Alert severity="info">
        Allowed only within the customer’s approved, available credit. Who and why are recorded.
      </Alert>
    </FormDialog>
  );
}

interface TransferValues {
  purchase_id: string;
  from_machine_id: string;
  to_machine_id: string;
  hours: string;
  reason: string;
  reason_code_id: string;
}

/** Request moving remaining hours of a purchase to another machine (decided by someone else). */
export function RequestTransferDialog({
  purchase,
  reasonCodeRequired = false,
  onClose,
  onDone,
}: {
  /** Fixed purchase (purchase page); omit to pick one (field work). */
  purchase?: HoursPurchaseDto;
  reasonCodeRequired?: boolean;
  onClose: () => void;
  onDone: (t: TransferDto) => void;
}) {
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(newUuid);
  const schema: ObjectSchema<TransferValues> = object({
    purchase_id: string().required('Choose the purchase'),
    from_machine_id: string().ensure(),
    to_machine_id: string().required('Choose the machine to transfer to'),
    hours: positiveDecimalField('Hours'),
    reason: reasonField(),
    reason_code_id: string()
      .ensure()
      .test('required', 'Choose a reason from the list', (v) => !reasonCodeRequired || v !== ''),
  });
  return (
    <FormDialog<TransferValues>
      open
      title={
        purchase === undefined
          ? 'Request hours transfer'
          : `Transfer hours from ${purchase.purchase_number}`
      }
      initialValues={{
        purchase_id: purchase?.id ?? '',
        from_machine_id: purchase?.machine_id ?? '',
        to_machine_id: '',
        hours: '',
        reason: '',
        reason_code_id: '',
      }}
      validationSchema={schema}
      submitLabel="Request transfer"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = {
          purchase_id: v.purchase_id,
          from_machine_id: orNull(v.from_machine_id),
          to_machine_id: v.to_machine_id,
          hours: v.hours.trim(),
          reason: v.reason.trim(),
          reason_code_id: orNull(v.reason_code_id),
          client_id: clientId,
        };
        try {
          onDone(await hoursRequestService.requestTransfer(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, HOURS_ERROR_HINTS);
        }
      }}
    >
      {purchase === undefined && (
        <FormikPurchaseIdPicker name="purchase_id" label="Hours purchase" required />
      )}
      <FormikMachineIdPicker
        name="from_machine_id"
        label="From machine"
        helperText="Empty = the purchase’s machine."
      />
      <FormikMachineIdPicker name="to_machine_id" label="To machine" required />
      <FormikTextField name="hours" label="Hours" required slotProps={decimal} />
      <FormikReasonCodePicker
        name="reason_code_id"
        kind="TRANSFER"
        label="Reason from your list"
        required={reasonCodeRequired}
      />
      <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
    </FormDialog>
  );
}
