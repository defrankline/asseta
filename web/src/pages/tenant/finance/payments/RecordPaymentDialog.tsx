import { Alert, Box, Typography } from '@mui/material';
import { useState } from 'react';
import { cashService } from '../../../../api/services/cashService';
import { customerPaymentService } from '../../../../api/services/financeService';
import { newUuid } from '../../../../api/ids';
import type {
  CustomerDto,
  CustomerPaymentDto,
  HireInvoiceDto,
  StaffDto,
} from '../../../../api/types';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { FormikDateTimeField } from '../../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../../utils/time';
import { withErrorCode } from '../../shared/errorHints';
import {
  CURRENCY_OPTIONS,
  FINANCE_ERROR_HINTS,
  PAYMENT_METHOD_LABELS,
  PAYMENT_METHOD_OPTIONS,
} from '../../shared/financeDisplay';
import { customerOptionLabel, invoiceOptionLabel } from '../../shared/financeLookups';
import { FormikCustomerIdPicker, FormikStaffIdPicker } from '../../shared/financePickers';
import { AllocationFields } from './AllocationFields';
import {
  ALLOCATION_FIELDS,
  emptyPaymentValues,
  PAYMENT_FIELDS,
  paymentFormSchema,
  RECEIPT_FIELDS,
  REFERENCE_REQUIRED,
  toCollectionPayload,
  toPaymentPayload,
  type PaymentFormValues,
} from './paymentForm';

export type PaymentMode = 'payment' | 'collection';

interface RecordPaymentDialogProps {
  /** `collection`: a supervisor's CASH collection into custody (recordCashCollection). */
  mode?: PaymentMode;
  customerId?: string;
  /** Pre-fills one allocation to this issued invoice. */
  invoice?: HireInvoiceDto;
  /** Pre-fills the custodian of a cash collection. */
  staffMemberId?: string;
  timeZone: string;
  onClose: () => void;
  onRecorded: (payment: CustomerPaymentDto) => void;
}

/**
 * Payment → Receipt → Allocation → Review. Recorded money is CLAIMED until someone other than the
 * recorder verifies it; only VERIFIED money reduces balances. Mount only while open.
 */
export function RecordPaymentDialog({
  mode = 'payment',
  customerId,
  invoice,
  staffMemberId,
  timeZone,
  onClose,
  onRecorded,
}: RecordPaymentDialogProps) {
  const keyFor = useIdempotencyKey();
  /** Device/client id fixed per dialog open: a retry replays instead of duplicating. */
  const [clientId] = useState(() => newUuid());
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [staff, setStaff] = useState<StaffDto | null>(null);
  const isCollection = mode === 'collection';
  const [initialValues] = useState(() => ({
    ...emptyPaymentValues(new Date().toISOString(), {
      ...(customerId !== undefined ? { customerId } : {}),
      ...(invoice !== undefined ? { invoice } : {}),
      method: isCollection ? 'CASH' : 'BANK',
    }),
    received_by_staff_id: staffMemberId ?? '',
  }));
  const steps: FormStep<PaymentFormValues>[] = [
    {
      label: 'Payment',
      fields: PAYMENT_FIELDS,
      render: (formik) => (
        <>
          <FormikCustomerIdPicker
            name="customer_id"
            label="Customer"
            required
            onOptionChange={setCustomer}
          />
          {!isCollection && (
            <FormikSelectField
              name="method"
              label="Method"
              options={PAYMENT_METHOD_OPTIONS}
              required
            />
          )}
          <FormikTextField
            name="amount"
            label="Amount"
            required
            slotProps={{ htmlInput: { inputMode: 'decimal' } }}
          />
          <FormikSelectField
            name="currency"
            label="Currency"
            options={CURRENCY_OPTIONS}
            helperText="Must match the invoices it pays."
          />
          <FormikTextField
            name="reference"
            label={
              REFERENCE_REQUIRED.has(formik.values.method)
                ? 'Transaction reference'
                : 'Reference (optional, e.g. receipt book number)'
            }
            required={REFERENCE_REQUIRED.has(formik.values.method)}
            helperText="Bank and mobile money payments need the transaction reference; a method + reference pair is unique."
          />
        </>
      ),
    },
    {
      label: 'Receipt',
      fields: RECEIPT_FIELDS,
      render: () => (
        <>
          <FormikDateTimeField
            name="received_at"
            label="Received at"
            timeZone={timeZone}
            required
          />
          <FormikStaffIdPicker
            name="received_by_staff_id"
            label={isCollection ? 'Collected by (custodian)' : 'Received by (optional)'}
            supervisorsOnly={isCollection}
            onOptionChange={setStaff}
            helperText={
              isCollection
                ? 'Leave empty for your own custody. Naming someone else needs office cash permission (NOT_CUSTODIAN otherwise).'
                : 'Staff member who received the money, if any.'
            }
          />
          <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
        </>
      ),
    },
    {
      label: 'Allocation',
      fields: ALLOCATION_FIELDS,
      render: () => <AllocationFields />,
    },
  ];
  return (
    <StepperFormDialog<PaymentFormValues>
      open
      title={isCollection ? 'Record cash collection' : 'Record customer payment'}
      steps={steps}
      initialValues={initialValues}
      validationSchema={paymentFormSchema}
      submitLabel={isCollection ? 'Record collection' : 'Record payment'}
      onClose={onClose}
      renderReview={(v) => (
        <Box className="flex flex-col gap-3">
          <KeyValueGrid
            columns={2}
            items={[
              {
                label: 'Customer',
                value: customer === null ? v.customer_id : customerOptionLabel(customer),
              },
              { label: 'Method', value: PAYMENT_METHOD_LABELS[v.method] },
              {
                label: 'Amount',
                value:
                  v.currency === '' ? (
                    `${v.amount} (tenant base currency)`
                  ) : (
                    <MoneyText amount={v.amount} currency={v.currency} strong />
                  ),
              },
              { label: 'Reference', value: v.reference.trim() || '—' },
              { label: 'Received at', value: formatInstantIn(v.received_at, timeZone) },
              {
                label: isCollection ? 'Custodian' : 'Received by',
                value: staff?.full_name ?? (isCollection ? 'Me (my custody)' : '—'),
              },
            ]}
          />
          <Typography variant="subtitle2">Allocations</Typography>
          {v.allocations.length === 0 ? (
            <Typography variant="body2">None — held as customer credit once verified.</Typography>
          ) : (
            v.allocations.map((a, i) => (
              <Box key={i} className="flex justify-between gap-2">
                <span>{a.invoice === null ? '—' : invoiceOptionLabel(a.invoice)}</span>
                <MoneyText amount={a.amount} currency={v.currency} />
              </Box>
            ))
          )}
          <Alert severity="info">
            Recorded as <strong>CLAIMED</strong>. It reduces the customer’s balance only after a
            different authorised person verifies it (segregation of duties).
          </Alert>
        </Box>
      )}
      onSubmit={async (v) => {
        try {
          if (isCollection) {
            const body = toCollectionPayload(v, clientId);
            onRecorded(await cashService.recordCollection(body, keyFor(body)));
          } else {
            const body = toPaymentPayload(v, clientId);
            onRecorded(await customerPaymentService.record(body, keyFor(body)));
          }
        } catch (err) {
          throw withErrorCode(err, FINANCE_ERROR_HINTS);
        }
      }}
    />
  );
}
