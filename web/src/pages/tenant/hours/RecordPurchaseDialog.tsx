import {
  Alert,
  Button,
  FormControl,
  FormControlLabel,
  FormLabel,
  Radio,
  RadioGroup,
  Stack,
  Typography,
} from '@mui/material';
import { useFormikContext } from 'formik';
import { useCallback, useEffect, useRef, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import type { HoursPurchaseDto, HoursQuoteDto } from '../../../api/hoursTypes';
import { newIdempotencyKey, newUuid } from '../../../api/ids';
import { hoursService } from '../../../api/services/hoursService';
import type { CustomerDto, MachineDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikDateTimeField } from '../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog } from '../../../components/forms/StepperFormDialog';
import { AttachmentUpload } from '../../../components/meter/AttachmentUpload';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { withErrorCode } from '../shared/errorHints';
import { PAYMENT_METHOD_LABELS, PAYMENT_METHOD_OPTIONS } from '../shared/financeDisplay';
import { customerOptionLabel, machineOptionLabel } from '../shared/financeLookups';
import {
  FormikCustomerIdPicker,
  FormikMachineIdPicker,
  FormikStaffIdPicker,
} from '../shared/financePickers';
import { FormikJobSitePicker } from '../shared/lookupPickers';
import { HOURS_ERROR_HINTS } from './hoursDisplay';
import { money, paidSummary, remainingBalance } from './hoursQuote';
import { HoursQuoteLine } from './HoursQuoteLine';
import {
  CUSTOMER_FIELDS,
  emptyPaymentLine,
  followTotal,
  emptyPurchaseValues,
  HOURS_FIELDS,
  MAX_PAYMENT_LINES,
  NEEDS_REFERENCE,
  OVER_TOTAL_TEXT,
  paidSoFar,
  PAYMENT_FIELDS,
  paymentFieldsFor,
  purchaseSchema,
  toPurchasePayload,
  type PurchaseValues,
} from './purchaseForm';

const CASH_ONLY_OPTIONS = PAYMENT_METHOD_OPTIONS.filter((o) => o.value === 'CASH');
const decimal = { htmlInput: { inputMode: 'decimal' as const } };

function CustomerStep({
  walkInAllowed,
  onCustomer,
}: {
  walkInAllowed: boolean;
  onCustomer: (c: CustomerDto | null) => void;
}) {
  const { values, setFieldValue } = useFormikContext<PurchaseValues>();
  return (
    <>
      {walkInAllowed && (
        <FormControl>
          <FormLabel id="customer-mode-label">Customer</FormLabel>
          <RadioGroup
            row
            aria-labelledby="customer-mode-label"
            value={values.customer_mode}
            onChange={(e) => {
              void setFieldValue('customer_mode', e.target.value);
            }}
          >
            <FormControlLabel value="EXISTING" control={<Radio />} label="Existing customer" />
            <FormControlLabel value="WALK_IN" control={<Radio />} label="New walk-in customer" />
          </RadioGroup>
        </FormControl>
      )}
      {values.customer_mode === 'EXISTING' ? (
        <FormikCustomerIdPicker
          name="customer_id"
          label="Customer"
          required
          onOptionChange={onCustomer}
        />
      ) : (
        <>
          <FormikTextField name="walk_in_name" label="Walk-in customer name" required />
          <FormikTextField name="walk_in_phone" label="Phone (optional)" />
          <Typography variant="body2" color="text.secondary">
            A walk-in gets a WALK- code; the office can register them as a full customer later.
          </Typography>
        </>
      )}
    </>
  );
}

function quoteCustomerId(v: PurchaseValues): string {
  return v.customer_mode === 'EXISTING' ? v.customer_id : '';
}

/**
 * Keeps the quote total in the form so the payments can be checked against it, and sets the
 * opening Cash line to the total until the user types into its amount.
 */
function useQuoteSync(): (q: HoursQuoteDto | null) => void {
  const { values, setFieldValue } = useFormikContext<PurchaseValues>();
  const payments = useRef(values.payments);
  useEffect(() => {
    payments.current = values.payments;
  });
  return useCallback(
    (q: HoursQuoteDto | null) => {
      void setFieldValue('quote_amount', q?.amount ?? '', false);
      void setFieldValue('quote_currency', q?.currency ?? '', false);
      const followed = followTotal(payments.current, q?.amount ?? '');
      if (followed !== null) void setFieldValue('payments', followed, false);
    },
    [setFieldValue],
  );
}

/** The live total under the Hours field. */
function HoursStepQuote() {
  const { values } = useFormikContext<PurchaseValues>();
  const onQuote = useQuoteSync();
  return (
    <HoursQuoteLine
      machineId={values.machine_id}
      hours={values.hours}
      customerId={quoteCustomerId(values)}
      onQuote={onQuote}
    />
  );
}

function PaymentLineFields({
  index,
  field,
  timeZone,
  nonCashAllowed,
}: {
  index: number;
  field: boolean;
  timeZone: string;
  nonCashAllowed: boolean;
}) {
  const { values, setFieldValue } = useFormikContext<PurchaseValues>();
  const line = values.payments[index];
  if (line === undefined) return null;
  const at = (f: string) => `payments[${index}].${f}`;
  const remove = () => {
    void setFieldValue(
      'payments',
      values.payments.filter((_, i) => i !== index),
    );
  };
  return (
    <Stack spacing={1.5} sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5 }}>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="subtitle2">Payment {index + 1}</Typography>
        <Button
          size="small"
          color="inherit"
          onClick={remove}
          aria-label={`Remove payment ${index + 1}`}
        >
          Remove
        </Button>
      </Stack>
      {nonCashAllowed ? (
        <FormikSelectField
          name={at('method')}
          label="Method"
          options={PAYMENT_METHOD_OPTIONS}
          required
        />
      ) : (
        <FormikSelectField
          name={at('method')}
          label="Method"
          options={CASH_ONLY_OPTIONS}
          required
        />
      )}
      <FormikTextField
        name={at('amount')}
        label="Amount"
        required
        slotProps={decimal}
        onInput={() => {
          // Typed into: the amount no longer follows the total.
          if (line.follows_total) void setFieldValue(at('follows_total'), false, false);
        }}
      />
      {NEEDS_REFERENCE.has(line.method) && (
        <FormikTextField
          name={at('reference')}
          label="Reference (receipt or transaction no.)"
          required
        />
      )}
      <FormikDateTimeField
        name={at('received_at')}
        label="Received at"
        timeZone={timeZone}
        required
      />
      {!field && line.method === 'CASH' && (
        <FormikStaffIdPicker
          name={at('staff_member_id')}
          label="Cash held by (empty = me)"
          helperText="The staff member who holds the money until it is handed over."
        />
      )}
      <AttachmentUpload
        label="Evidence photo (receipt or mobile-money screenshot)"
        value={line.evidence}
        onChange={(a) => {
          void setFieldValue(at('evidence'), a);
        }}
        upload={(file) => hoursService.uploadEvidence(file, newIdempotencyKey())}
        capture="environment"
        preview
        helperText="Kept as evidence only; the payment stays claimed until someone else verifies it."
      />
    </Stack>
  );
}

function PaymentStep({
  field,
  timeZone,
  nonCashAllowed,
}: {
  field: boolean;
  timeZone: string;
  nonCashAllowed: boolean;
}) {
  const { values, setFieldValue } = useFormikContext<PurchaseValues>();
  const onQuote = useQuoteSync();
  const paid = paidSoFar(values.payments);
  const add = () => {
    const amount = remainingBalance(paid, values.quote_amount);
    void setFieldValue('payments', [
      ...values.payments,
      emptyPaymentLine('CASH', amount, new Date().toISOString()),
    ]);
  };
  return (
    <>
      <HoursQuoteLine
        machineId={values.machine_id}
        hours={values.hours}
        customerId={quoteCustomerId(values)}
        onQuote={onQuote}
      />
      {values.payments.map((l, i) => (
        <PaymentLineFields
          key={l.key}
          index={i}
          field={field}
          timeZone={timeZone}
          nonCashAllowed={nonCashAllowed}
        />
      ))}
      <PaidSummary values={values} />
      {values.payments.length < MAX_PAYMENT_LINES && (
        <Button variant="outlined" onClick={add} sx={{ alignSelf: 'flex-start' }}>
          Add payment
        </Button>
      )}
      {!nonCashAllowed && (
        <Typography variant="body2" color="text.secondary">
          Bank and mobile-money payments are recorded by the office.
        </Typography>
      )}
      {values.payments.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          Hours stay awaiting payment until money is recorded and verified (or activated on credit).
        </Typography>
      )}
    </>
  );
}

/** Live "Paid … of … · Balance …" with the status, and the over-total block. */
function PaidSummary({ values }: { values: PurchaseValues }) {
  const paid = paidSoFar(values.payments);
  if (values.quote_amount === '') {
    if (values.payments.length === 0) return null;
    return (
      <Typography variant="body2" color="text.secondary">
        Paid {paid} (the total is not known yet)
      </Typography>
    );
  }
  const sum = paidSummary(paid, values.quote_amount, values.quote_currency);
  return (
    <>
      <Typography variant="body2" sx={{ fontWeight: 600 }} role="status">
        {sum.line}
      </Typography>
      {sum.over ? (
        <Alert severity="error">{OVER_TOTAL_TEXT}</Alert>
      ) : (
        <Typography variant="body2" color="text.secondary">
          {sum.status}
        </Typography>
      )}
    </>
  );
}

interface RecordPurchaseDialogProps {
  timeZone: string;
  /** Field work: the payment is in the recorder's own custody (no "held by" choice). */
  field?: boolean;
  walkInAllowed: boolean;
  /** CUSTOMER_HOURS field_noncash_payments: collection recorders may take bank and mobile money. */
  fieldNoncashPayments?: boolean;
  onClose: () => void;
  onRecorded: (purchase: HoursPurchaseDto) => void;
}

/** Customer → Hours → Payment → Review. Priced by the server (rate card, approved discount). */
export function RecordPurchaseDialog({
  timeZone,
  field = false,
  walkInAllowed,
  fieldNoncashPayments = false,
  onClose,
  onRecorded,
}: RecordPurchaseDialogProps) {
  const keyFor = useIdempotencyKey();
  const { hasPermission } = useSession();
  const [clientId] = useState(newUuid);
  const [initial] = useState(emptyPurchaseValues);
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const nonCashAllowed =
    hasPermission(PERMISSIONS.tenantFinancePayment) ||
    (fieldNoncashPayments && hasPermission(PERMISSIONS.tenantCollectionRecord));
  return (
    <StepperFormDialog<PurchaseValues>
      open
      title={field ? 'Record customer hours' : 'New hours purchase'}
      initialValues={initial}
      validationSchema={purchaseSchema}
      submitLabel="Record purchase"
      onClose={onClose}
      steps={[
        {
          label: 'Customer',
          fields: CUSTOMER_FIELDS,
          render: () => <CustomerStep walkInAllowed={walkInAllowed} onCustomer={setCustomer} />,
        },
        {
          label: 'Hours',
          fields: HOURS_FIELDS,
          render: () => (
            <>
              <FormikMachineIdPicker
                name="machine_id"
                label="Machine"
                required
                onOptionChange={setMachine}
              />
              <FormikTextField name="hours" label="Hours bought" required slotProps={decimal} />
              <HoursStepQuote />
              {hasPermission(PERMISSIONS.tenantGeofenceRead) && (
                <FormikJobSitePicker name="job_site_id" label="Job site (optional)" />
              )}
              <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
              <Typography variant="body2" color="text.secondary">
                The price comes from your rate card and any approved discount for this customer.
              </Typography>
            </>
          ),
        },
        {
          label: 'Payment',
          fields: PAYMENT_FIELDS,
          fieldsFor: paymentFieldsFor,
          render: () => (
            <PaymentStep field={field} timeZone={timeZone} nonCashAllowed={nonCashAllowed} />
          ),
        },
      ]}
      renderReview={(v) => (
        <>
          <KeyValueGrid
            columns={2}
            items={[
              {
                label: 'Customer',
                value:
                  v.customer_mode === 'WALK_IN'
                    ? `${v.walk_in_name.trim()} (walk-in)`
                    : customer !== null
                      ? customerOptionLabel(customer)
                      : v.customer_id,
              },
              {
                label: 'Machine',
                value: machine !== null ? machineOptionLabel(machine) : v.machine_id,
              },
              { label: 'Hours', value: `${v.hours.trim()} h` },
              ...(v.payments.length === 0
                ? [{ label: 'Payment', value: 'Not paid yet' }]
                : v.payments.map((l, i) => ({
                    label: `Payment ${i + 1}`,
                    value: [
                      PAYMENT_METHOD_LABELS[l.method],
                      v.quote_currency === ''
                        ? l.amount.trim()
                        : money(l.amount.trim(), v.quote_currency),
                      l.reference.trim() === '' ? null : `ref ${l.reference.trim()}`,
                      formatInstantIn(l.received_at, timeZone),
                      l.evidence === null ? null : 'photo attached',
                    ]
                      .filter((x) => x !== null)
                      .join(' · '),
                  }))),
            ]}
          />
          <HoursQuoteLine
            machineId={v.machine_id}
            hours={v.hours}
            customerId={quoteCustomerId(v)}
          />
          <PaidSummary values={v} />
          <Alert severity="info">
            Hours activate only from verified money: someone other than you verifies the payment.
          </Alert>
        </>
      )}
      onSubmit={async (v) => {
        const body = toPurchasePayload(v, clientId, { field });
        try {
          onRecorded(await hoursService.recordPurchase(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, HOURS_ERROR_HINTS);
        }
      }}
    />
  );
}
