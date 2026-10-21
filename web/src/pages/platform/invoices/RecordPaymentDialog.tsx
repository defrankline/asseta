import { Alert, Box } from '@mui/material';
import { useState } from 'react';
import { mixed, object, string } from 'yup';
import { platformPaymentService } from '../../../api/services/platformPaymentService';
import type { InvoiceDto, PaymentDto, PaymentMethod, RecordPaymentIn } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikDateField } from '../../../components/forms/FormikDateField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatDate, todayIsoDate } from '../../../utils/dates';
import { compareDecimal, formatMoney, isDecimalString } from '../../../utils/money';
import { optionLabel, PAYMENT_METHOD_OPTIONS } from '../shared/billingDisplay';
import { isoDateField, positiveDecimalField } from '../shared/validators';

interface RecordPaymentValues {
  method: PaymentMethod;
  reference: string;
  received_on: string;
  amount: string;
}

function buildSchema(balance: string) {
  return object({
    method: mixed<PaymentMethod>()
      .oneOf(['CASH', 'BANK_TRANSFER', 'MOBILE_MONEY'])
      .required('Method is required'),
    reference: string()
      .trim()
      .required('Reference is required')
      .min(2, 'Reference must be at least 2 characters')
      .max(120, 'Reference must be at most 120 characters'),
    received_on: isoDateField('Received on'),
    amount: positiveDecimalField('Amount').test(
      'not-over-balance',
      'Amount cannot exceed the outstanding balance',
      (v) => !isDecimalString(v) || compareDecimal(v, balance) <= 0,
    ),
  });
}

interface RecordPaymentDialogProps {
  invoice: InvoiceDto & { id: string };
  onClose: () => void;
  onRecorded: (payment: PaymentDto) => void;
}

/** Records a manual payment against an invoice; currency is fixed to the invoice currency. */
export function RecordPaymentDialog({ invoice, onClose, onRecorded }: RecordPaymentDialogProps) {
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState<RecordPaymentValues>(() => ({
    method: 'BANK_TRANSFER',
    reference: '',
    received_on: todayIsoDate(),
    amount: '',
  }));
  const [schema] = useState(() => buildSchema(invoice.balance));
  const today = todayIsoDate();

  return (
    <StepperFormDialog<RecordPaymentValues>
      open
      title={`Record payment · ${invoice.invoice_number ?? ''}`}
      maxWidth="sm"
      initialValues={initialValues}
      validationSchema={schema}
      submitLabel="Record payment"
      onClose={onClose}
      steps={[
        {
          label: 'Payment',
          fields: ['method', 'reference', 'received_on', 'amount'],
          render: () => (
            <>
              <Alert severity="info">
                Outstanding balance {formatMoney(invoice.balance, invoice.currency)}. The payment
                stays RECORDED until verified; only verified payments reduce the balance.
              </Alert>
              <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormikSelectField
                  name="method"
                  label="Method"
                  options={PAYMENT_METHOD_OPTIONS}
                  required
                />
                <FormikTextField
                  name="reference"
                  label="Reference"
                  required
                  helperText="Bank / mobile money ref., receipt no."
                />
                <FormikDateField name="received_on" label="Received on" required maxDate={today} />
                <FormikTextField
                  name="amount"
                  label={`Amount (${invoice.currency})`}
                  required
                  slotProps={{ htmlInput: { inputMode: 'decimal' } }}
                />
              </Box>
            </>
          ),
        },
      ]}
      renderReview={(v) => (
        <KeyValueGrid
          columns={2}
          items={[
            { label: 'Invoice', value: invoice.invoice_number ?? invoice.id },
            { label: 'Method', value: optionLabel(PAYMENT_METHOD_OPTIONS, v.method) },
            { label: 'Reference', value: v.reference.trim() },
            { label: 'Received on', value: formatDate(v.received_on) },
            {
              label: 'Amount',
              value: isDecimalString(v.amount) ? formatMoney(v.amount, invoice.currency) : v.amount,
            },
          ]}
        />
      )}
      onSubmit={async (v) => {
        const payload: RecordPaymentIn = {
          invoice_id: invoice.id,
          amount: v.amount.trim(),
          currency: invoice.currency,
          method: v.method,
          reference: v.reference.trim(),
          received_on: v.received_on,
        };
        onRecorded(await platformPaymentService.record(payload, keyFor(payload)));
      }}
    />
  );
}
