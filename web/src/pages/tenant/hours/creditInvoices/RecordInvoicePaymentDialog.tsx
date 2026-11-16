import { Alert, Button, Stack, Typography } from '@mui/material';
import { useFormikContext } from 'formik';
import { useState } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import type { CreditInvoiceDto } from '../../../../api/hoursTypes';
import { newIdempotencyKey, newUuid } from '../../../../api/ids';
import { creditInvoiceService } from '../../../../api/services/creditInvoiceService';
import { hoursService } from '../../../../api/services/hoursService';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { FormikDateTimeField } from '../../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { StepperFormDialog } from '../../../../components/forms/StepperFormDialog';
import { AttachmentUpload } from '../../../../components/meter/AttachmentUpload';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { useSession } from '../../../../session/useSession';
import { formatInstantIn } from '../../../../utils/time';
import { withErrorCode } from '../../shared/errorHints';
import { FormikStaffIdPicker } from '../../shared/financePickers';
import { money } from '../hoursQuote';
import { SALE_METHOD_CHOICES, SALE_METHOD_LABELS } from '../saleMethods';
import {
  DETAIL_FIELDS,
  emptyInvoicePayment,
  INVOICE_PAYMENT_HINTS,
  invoicePaymentSchema,
  PAY_FIELDS,
  toInvoicePaymentPayload,
  type InvoicePaymentValues,
} from './invoicePaymentForm';

const decimal = { htmlInput: { inputMode: 'decimal' as const } };

function PayStep({
  invoice,
  nonCashAllowed,
}: {
  invoice: CreditInvoiceDto;
  nonCashAllowed: boolean;
}) {
  const { values, setFieldValue } = useFormikContext<InvoicePaymentValues>();
  const full = values.amount.trim() === invoice.balance;
  return (
    <>
      <Typography variant="body2">
        Balance to pay: <strong>{money(invoice.balance, invoice.currency)}</strong> (due{' '}
        {invoice.due_date})
      </Typography>
      <FormikTextField
        name="amount"
        label="Amount received"
        required
        slotProps={decimal}
        helperText={full ? 'Pays the invoice in full.' : 'A part payment; the rest stays owed.'}
      />
      {!full && (
        <Button
          size="small"
          sx={{ alignSelf: 'flex-start' }}
          onClick={() => {
            void setFieldValue('amount', invoice.balance);
          }}
        >
          Pay the full balance
        </Button>
      )}
      <FormikSelectField
        name="method"
        label="Method"
        options={SALE_METHOD_CHOICES[nonCashAllowed ? 'ALL' : 'CASH']}
        required
      />
      {values.method !== 'CASH' && (
        <FormikTextField name="reference" label="Reference (receipt or transaction no.)" required />
      )}
      {!nonCashAllowed && (
        <Typography variant="body2" color="text.secondary">
          Bank and mobile-money payments are recorded by the office.
        </Typography>
      )}
    </>
  );
}

function DetailsStep({ timeZone, office }: { timeZone: string; office: boolean }) {
  const { values, setFieldValue } = useFormikContext<InvoicePaymentValues>();
  return (
    <>
      <FormikDateTimeField name="received_at" label="Received at" timeZone={timeZone} required />
      {office && values.method === 'CASH' && (
        <FormikStaffIdPicker
          name="staff_member_id"
          label="Cash held by (empty = me)"
          helperText="The staff member who holds the money until it is handed over."
        />
      )}
      <AttachmentUpload
        label="Evidence photo (receipt or mobile-money screenshot)"
        value={values.evidence}
        onChange={(a) => {
          void setFieldValue('evidence', a);
        }}
        upload={(file) => hoursService.uploadEvidence(file, newIdempotencyKey())}
        capture="environment"
        preview
        helperText="Kept as evidence; bank and mobile money stay claimed until someone else verifies them."
      />
      <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
    </>
  );
}

interface RecordInvoicePaymentDialogProps {
  invoice: CreditInvoiceDto;
  timeZone: string;
  /** CUSTOMER_HOURS field_noncash_payments: field staff may take bank and mobile money. */
  fieldNoncashPayments: boolean;
  onClose: () => void;
  onRecorded: (invoice: CreditInvoiceDto) => void;
}

/** Payment → Details → Review. Cash goes into the recorder's (or the named holder's) cash custody. */
export function RecordInvoicePaymentDialog({
  invoice,
  timeZone,
  fieldNoncashPayments,
  onClose,
  onRecorded,
}: RecordInvoicePaymentDialogProps) {
  const keyFor = useIdempotencyKey();
  const { hasPermission } = useSession();
  const [clientId] = useState(newUuid);
  const [initial] = useState(() => emptyInvoicePayment(invoice.balance, new Date().toISOString()));
  const office = hasPermission(PERMISSIONS.tenantFinancePayment);
  const nonCashAllowed = office || fieldNoncashPayments;
  return (
    <StepperFormDialog<InvoicePaymentValues>
      open
      title={`Record payment · ${invoice.invoice_number}`}
      initialValues={initial}
      validationSchema={invoicePaymentSchema}
      submitLabel="Record payment"
      onClose={onClose}
      steps={[
        {
          label: 'Payment',
          fields: PAY_FIELDS,
          render: () => <PayStep invoice={invoice} nonCashAllowed={nonCashAllowed} />,
        },
        {
          label: 'Details',
          fields: DETAIL_FIELDS,
          render: () => <DetailsStep timeZone={timeZone} office={office} />,
        },
      ]}
      renderReview={(v) => (
        <Stack spacing={2}>
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Invoice', value: invoice.invoice_number },
              { label: 'Customer', value: invoice.customer_name ?? invoice.customer_id },
              { label: 'Amount', value: money(v.amount.trim(), invoice.currency) },
              {
                label: 'Kind',
                value: v.amount.trim() === invoice.balance ? 'Full payment' : 'Part payment',
              },
              { label: 'Method', value: SALE_METHOD_LABELS[v.method] },
              ...(v.method === 'CASH' ? [] : [{ label: 'Reference', value: v.reference.trim() }]),
              { label: 'Received at', value: formatInstantIn(v.received_at, timeZone) },
              { label: 'Evidence', value: v.evidence === null ? 'None' : 'Photo attached' },
            ]}
          />
          <Alert severity="info">
            {v.method === 'CASH'
              ? 'The cash goes into your cash custody (or the named holder’s) until it is handed over.'
              : 'The payment stays claimed until someone other than you verifies it.'}
          </Alert>
        </Stack>
      )}
      onSubmit={async (v) => {
        const body = toInvoicePaymentPayload(v, clientId, { office });
        try {
          onRecorded(await creditInvoiceService.recordPayment(invoice.id, body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, INVOICE_PAYMENT_HINTS);
        }
      }}
    />
  );
}
