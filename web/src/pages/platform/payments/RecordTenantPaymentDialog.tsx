import { Alert, Box } from '@mui/material';
import { useCallback, useState } from 'react';
import { mixed, object, string, type ObjectSchema } from 'yup';
import { platformPaymentService } from '../../../api/services/platformPaymentService';
import type {
  InvoiceDto,
  PaymentDto,
  PaymentMethod,
  RecordPaymentIn,
  TenantDto,
} from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { FormikDateField } from '../../../components/forms/FormikDateField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatDate, todayIsoDate } from '../../../utils/dates';
import { formatMoney, isDecimalString, SUPPORTED_CURRENCIES } from '../../../utils/money';
import { CURRENCY_OPTIONS, optionLabel, PAYMENT_METHOD_OPTIONS } from '../shared/billingDisplay';
import { resolveTenant, searchTenants, tenantId, tenantLabel } from '../shared/platformLookups';
import { isoDateField, positiveDecimalField } from '../shared/validators';
import { invoiceId, invoiceLabel, resolveInvoice, searchOpenInvoices } from './paymentLookups';

interface Values {
  tenant_id: string;
  invoice_id: string;
  method: PaymentMethod;
  reference: string;
  received_on: string;
  currency: string;
  amount: string;
}

const schema: ObjectSchema<Values> = object({
  tenant_id: string().required('Choose a tenant'),
  invoice_id: string().ensure(),
  method: mixed<PaymentMethod>()
    .oneOf(['CASH', 'BANK_TRANSFER', 'MOBILE_MONEY'])
    .required('Method is required'),
  reference: string()
    .trim()
    .required('Reference is required')
    .min(2, 'Reference must be at least 2 characters')
    .max(120, 'Reference must be at most 120 characters'),
  received_on: isoDateField('Received on'),
  currency: string()
    .oneOf([...SUPPORTED_CURRENCIES], 'Choose a currency')
    .required(),
  amount: positiveDecimalField('Amount'),
});

interface Props {
  onClose: () => void;
  onRecorded: (payment: PaymentDto) => void;
}

/**
 * Record a payment received from a tenant, optionally for one invoice. Without an invoice the
 * verified money fills the tenant's oldest open invoices first; any surplus stays tenant credit.
 */
export function RecordTenantPaymentDialog({ onClose, onRecorded }: Props) {
  const keyFor = useIdempotencyKey();
  const [tenant, setTenant] = useState<TenantDto | null>(null);
  const [invoice, setInvoice] = useState<InvoiceDto | null>(null);
  const [initialValues] = useState<Values>(() => ({
    tenant_id: '',
    invoice_id: '',
    method: 'BANK_TRANSFER',
    reference: '',
    received_on: todayIsoDate(),
    currency: 'TZS',
    amount: '',
  }));
  const openInvoices = useCallback(
    (q: string, signal: AbortSignal) =>
      tenant === null ? Promise.resolve([]) : searchOpenInvoices(tenant.id)(q, signal),
    [tenant],
  );

  return (
    <StepperFormDialog<Values>
      open
      title="Record payment"
      initialValues={initialValues}
      validationSchema={schema}
      submitLabel="Record payment"
      onClose={onClose}
      steps={[
        {
          label: 'Tenant & invoice',
          fields: ['tenant_id', 'invoice_id'],
          render: (f) => (
            <>
              <FormikAsyncIdAutocomplete<TenantDto>
                name="tenant_id"
                label="Tenant"
                required
                fetchOptions={searchTenants}
                resolveOption={resolveTenant}
                getOptionId={tenantId}
                getOptionLabel={tenantLabel}
                onOptionChange={(t) => {
                  setTenant(t);
                  if (t?.id !== tenant?.id) void f.setFieldValue('invoice_id', '');
                }}
              />
              <FormikAsyncIdAutocomplete<InvoiceDto>
                name="invoice_id"
                label="Invoice (optional)"
                disabled={f.values.tenant_id === ''}
                fetchOptions={openInvoices}
                resolveOption={resolveInvoice}
                getOptionId={invoiceId}
                getOptionLabel={invoiceLabel}
                onOptionChange={(i) => {
                  setInvoice(i);
                  if (i !== null) void f.setFieldValue('currency', i.currency);
                }}
                helperText="Leave empty to apply the money to the tenant's oldest open invoices."
                noOptionsText="No open invoices"
              />
            </>
          ),
        },
        {
          label: 'Payment',
          fields: ['method', 'reference', 'received_on', 'currency', 'amount'],
          render: (f) => (
            <>
              <Alert severity="info">
                The payment stays RECORDED until verified; only verified money is allocated to
                invoice lines and fulfils them.
              </Alert>
              <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormikSelectField name="method" label="Method" options={PAYMENT_METHOD_OPTIONS} />
                <FormikTextField name="reference" label="Reference" required />
                <FormikDateField
                  name="received_on"
                  label="Received on"
                  required
                  maxDate={todayIsoDate()}
                />
                <FormikSelectField
                  name="currency"
                  label="Currency"
                  options={CURRENCY_OPTIONS}
                  disabled={f.values.invoice_id !== ''}
                />
                <FormikTextField
                  name="amount"
                  label={`Amount (${f.values.currency})`}
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
            { label: 'Tenant', value: tenant?.display_name ?? v.tenant_id },
            {
              label: 'Applied to',
              value:
                v.invoice_id === ''
                  ? 'Oldest open invoices (surplus stays tenant credit)'
                  : (invoice?.invoice_number ?? v.invoice_id),
            },
            { label: 'Method', value: optionLabel(PAYMENT_METHOD_OPTIONS, v.method) },
            { label: 'Reference', value: v.reference.trim() },
            { label: 'Received on', value: formatDate(v.received_on) },
            {
              label: 'Amount',
              value: isDecimalString(v.amount) ? formatMoney(v.amount, v.currency) : v.amount,
            },
          ]}
        />
      )}
      onSubmit={async (v) => {
        const body: RecordPaymentIn = {
          ...(v.invoice_id === '' ? { tenant_id: v.tenant_id } : { invoice_id: v.invoice_id }),
          amount: v.amount.trim(),
          currency: v.currency,
          method: v.method,
          reference: v.reference.trim(),
          received_on: v.received_on,
        };
        onRecorded(await platformPaymentService.record(body, keyFor(body)));
      }}
    />
  );
}
