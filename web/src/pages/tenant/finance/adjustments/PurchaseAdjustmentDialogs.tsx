import { Alert, Typography } from '@mui/material';
import { useState } from 'react';
import { mixed, string } from 'yup';
import type { AdjustmentRequestDto, RefundSettlement } from '../../../../api/adjustmentTypes';
import type { HoursPurchaseDto, LedgerEntryDto } from '../../../../api/hoursTypes';
import { adjustmentService } from '../../../../api/services/adjustmentService';
import { hoursService } from '../../../../api/services/hoursService';
import type { HirePaymentMethod } from '../../../../api/types';
import { LOOKUP_PAGE_SIZE } from '../../../../components/data/AsyncAutocomplete';
import { FormikAsyncIdAutocomplete } from '../../../../components/forms/FormikAsyncIdAutocomplete';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { formatDate } from '../../../../utils/dates';
import { isDecimalString } from '../../../../utils/money';
import { positiveDecimalField } from '../../../platform/shared/validators';
import { hoursText } from '../../hours/hoursDisplay';
import { FormikMachineIdPicker, FormikStaffIdPicker } from '../../shared/financePickers';
import { PAYMENT_METHOD_OPTIONS } from '../../shared/financeDisplay';
import { optionId } from '../../shared/lookups';
import { orNull } from '../../shared/formRules';
import { AdjustmentProposalDialog } from './AdjustmentProposalDialog';
import { SETTLEMENT_OPTIONS } from './adjustmentDisplay';

const decimal = { htmlInput: { inputMode: 'decimal' as const } };

interface DialogProps {
  purchase: HoursPurchaseDto;
  onClose: () => void;
  onDone: (r: AdjustmentRequestDto) => void;
}

type Direction = 'ADD' | 'DEDUCT';
const DIRECTIONS = [
  { value: 'ADD', label: 'Add hours' },
  { value: 'DEDUCT', label: 'Take hours off' },
];

const entryLabel = (e: LedgerEntryDto): string =>
  [
    e.job_number ?? null,
    e.usage_day == null ? formatDate(e.occurred_at) : formatDate(e.usage_day),
    hoursText(e.hours),
  ]
    .filter((x) => x !== null)
    .join(' · ');

type CorrectionValues = {
  direction: Direction;
  hours: string;
  machine_id: string;
  consumed_entry_id: string;
};

type RefundValues = {
  hours: string;
  machine_id: string;
  settlement: RefundSettlement | '';
  method: HirePaymentMethod | '';
  reference: string;
  staff_member_id: string;
};

/** Propose adding hours to, or taking them off, one machine's lot of this purchase. */
export function CorrectHoursDialog({ purchase, onClose, onDone }: DialogProps) {
  const [consumedJob, setConsumedJob] = useState<string | null>(null);
  const correction = (v: CorrectionValues) => {
    const giveBack = v.direction === 'ADD' ? orNull(v.consumed_entry_id) : null;
    return {
      request_type: 'HOURS_CORRECTION' as const,
      purchase_id: purchase.id,
      machine_id: v.machine_id,
      hours: v.direction === 'ADD' ? v.hours.trim() : `-${v.hours.trim()}`,
      consumed_entry_id: giveBack,
      job_id: giveBack === null ? null : consumedJob,
    };
  };
  return (
    <AdjustmentProposalDialog<CorrectionValues, AdjustmentRequestDto>
      title={`Correct hours on ${purchase.purchase_number}`}
      submitLabel="Propose correction"
      reasonKind="CORRECTION"
      summary={
        <Typography variant="body2">
          Remaining: {hoursText(purchase.totals.remaining)}. The purchase is never edited; the
          correction is a new ledger entry that someone else decides.
        </Typography>
      }
      initial={{
        direction: 'ADD',
        hours: '',
        machine_id: purchase.machine_id,
        consumed_entry_id: '',
      }}
      shape={{
        direction: mixed<Direction>().oneOf(['ADD', 'DEDUCT']).required('Choose add or take off'),
        hours: positiveDecimalField('Hours'),
        machine_id: string().required('Choose the machine'),
        consumed_entry_id: string().ensure(),
      }}
      fields={(f) => (
        <>
          <FormikSelectField name="direction" label="Change" options={DIRECTIONS} required />
          <FormikTextField name="hours" label="Hours" required slotProps={decimal} />
          <FormikMachineIdPicker name="machine_id" label="Machine" required />
          {f.values.direction === 'ADD' && (
            <FormikAsyncIdAutocomplete<LedgerEntryDto>
              name="consumed_entry_id"
              label="Use of hours this gives back (optional)"
              fetchOptions={async (q, signal) =>
                (
                  await hoursService.listLedger(
                    {
                      page: 1,
                      page_size: LOOKUP_PAGE_SIZE,
                      q,
                      filters: { purchase_id: purchase.id, entry_type: 'CONSUMED' },
                    },
                    signal,
                  )
                ).items
              }
              getOptionId={optionId}
              getOptionLabel={entryLabel}
              onOptionChange={(e) => {
                setConsumedJob(e?.job_id ?? null);
              }}
              noOptionsText="No use of hours on this purchase matches"
            />
          )}
        </>
      )}
      forecast={(v) => (isDecimalString(v.hours.trim()) ? correction(v) : null)}
      submit={(common, v, key) => adjustmentService.propose({ ...common, ...correction(v) }, key)}
      onDone={onDone}
      onClose={onClose}
    />
  );
}

/** Propose refunding unused activated hours, as credit or as money paid out. */
export function RefundHoursDialog({ purchase, onClose, onDone }: DialogProps) {
  const refundReady = (v: RefundValues) =>
    isDecimalString(v.hours.trim()) &&
    v.settlement !== '' &&
    (v.settlement !== 'PAY_OUT' || v.method !== '');
  const refund = (v: RefundValues) => ({
    request_type: 'HOURS_REFUND' as const,
    purchase_id: purchase.id,
    machine_id: v.machine_id,
    hours: v.hours.trim(),
    settlement: v.settlement === '' ? null : v.settlement,
    payout:
      v.settlement === 'PAY_OUT' && v.method !== ''
        ? {
            method: v.method,
            reference: orNull(v.reference.trim()),
            staff_member_id: v.method === 'CASH' ? orNull(v.staff_member_id) : null,
          }
        : null,
  });
  return (
    <AdjustmentProposalDialog<RefundValues, AdjustmentRequestDto>
      title={`Refund unused hours of ${purchase.purchase_number}`}
      submitLabel="Propose refund"
      reasonKind="REFUND"
      summary={
        <Alert severity="info">
          Only unused hours can be refunded, up to the verified money on this purchase (
          {hoursText(purchase.totals.remaining)} remain). Someone else decides.
        </Alert>
      }
      initial={{
        hours: '',
        machine_id: purchase.machine_id,
        settlement: '',
        method: '',
        reference: '',
        staff_member_id: '',
      }}
      shape={{
        hours: positiveDecimalField('Hours'),
        machine_id: string().required('Choose the machine'),
        settlement: string().required('Choose how the refund is settled'),
        method: string()
          .ensure()
          .when('settlement', {
            is: 'PAY_OUT',
            then: (s) => s.required('Choose how it is paid out'),
          }),
        reference: string().ensure(),
        staff_member_id: string()
          .ensure()
          .when(['settlement', 'method'], {
            is: (settlement: string, method: string) =>
              settlement === 'PAY_OUT' && method === 'CASH',
            then: (s) => s.required('Choose who pays out the cash'),
          }),
      }}
      fields={(f) => (
        <>
          <FormikTextField name="hours" label="Hours to refund" required slotProps={decimal} />
          <FormikMachineIdPicker name="machine_id" label="Machine" required />
          <FormikSelectField
            name="settlement"
            label="Settlement"
            options={SETTLEMENT_OPTIONS}
            required
          />
          {f.values.settlement === 'PAY_OUT' && (
            <>
              <FormikSelectField
                name="method"
                label="Paid out by"
                options={PAYMENT_METHOD_OPTIONS}
                required
              />
              <FormikTextField name="reference" label="Payment reference" />
              {f.values.method === 'CASH' && (
                <FormikStaffIdPicker
                  name="staff_member_id"
                  label="Custodian paying the cash"
                  required
                />
              )}
            </>
          )}
        </>
      )}
      forecast={(v) => (refundReady(v) ? refund(v) : null)}
      submit={(common, v, key) => adjustmentService.propose({ ...common, ...refund(v) }, key)}
      onDone={onDone}
      onClose={onClose}
    />
  );
}

/** Propose reversing the whole purchase; the forecast shows on the request page. */
export function ReversePurchaseDialog({ purchase, onClose, onDone }: DialogProps) {
  return (
    <AdjustmentProposalDialog
      title={`Reverse ${purchase.purchase_number}`}
      submitLabel="Propose reversal"
      reasonKind="REVERSAL"
      initial={{}}
      summary={
        <Alert severity="warning">
          Unused hours come off and the money stays with the used hours it paid for; the rest
          returns to credit. Someone else decides.
        </Alert>
      }
      forecast={() => ({ request_type: 'PURCHASE_REVERSAL', purchase_id: purchase.id })}
      submit={(common, _v, key) =>
        adjustmentService.propose(
          { ...common, request_type: 'PURCHASE_REVERSAL', purchase_id: purchase.id },
          key,
        )
      }
      onDone={onDone}
      onClose={onClose}
    />
  );
}

/** A purchase with nothing to pay activates only once a second person approves it. */
export function ZeroAmountRequestDialog({ purchase, onClose, onDone }: DialogProps) {
  return (
    <AdjustmentProposalDialog
      title={`Ask to activate ${purchase.purchase_number}`}
      submitLabel="Send request"
      reasonKind="REVERSAL"
      initial={{}}
      summary={
        <Alert severity="info">
          This purchase has nothing to pay, so its hours stay inactive until someone else approves
          them.
        </Alert>
      }
      submit={(common, _v, key) =>
        adjustmentService.propose(
          { ...common, request_type: 'ZERO_AMOUNT_ACTIVATION', purchase_id: purchase.id },
          key,
        )
      }
      onDone={onDone}
      onClose={onClose}
    />
  );
}
