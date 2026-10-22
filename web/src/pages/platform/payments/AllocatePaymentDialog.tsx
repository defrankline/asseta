import { Alert, Box, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { mixed, object, string, type ObjectSchema } from 'yup';
import { withErrorCode } from '../../../api/lifecycle';
import { platformPaymentService } from '../../../api/services/platformPaymentService';
import type { InvoiceDto, InvoiceLineDto, LineAllocationIn, PaymentDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import {
  compareDecimal,
  formatMoney,
  isDecimalString,
  isZeroDecimal,
  sumDecimals,
} from '../../../utils/money';
import {
  invoiceId,
  invoiceLabel,
  lineRemaining,
  resolveInvoice,
  searchOpenInvoices,
} from './paymentLookups';

interface Values {
  invoice_id: string;
  amounts: Record<string, string>;
}

const DECIMAL = /^\d+(\.\d{1,4})?$/;

function openLines(invoice: InvoiceDto | null): (InvoiceLineDto & { id: string })[] {
  if (invoice === null) return [];
  return invoice.lines.filter(
    (l): l is InvoiceLineDto & { id: string } => l.id != null && lineRemaining(l) !== null,
  );
}

function buildSchema(invoice: InvoiceDto | null, unallocated: string): ObjectSchema<Values> {
  const lines = openLines(invoice);
  return object({
    invoice_id: string().ensure(),
    amounts: mixed<Record<string, string>>().required(),
  }).test('amounts', 'Invalid allocation', function check(v) {
    if (v.invoice_id === '') return true;
    const entered: string[] = [];
    for (const l of lines) {
      const a = (v.amounts[l.id] ?? '').trim();
      if (a === '') continue;
      const path = `amounts.${l.id}`;
      if (!DECIMAL.test(a)) {
        return this.createError({ path, message: 'A number with at most 4 decimal places' });
      }
      const remaining = lineRemaining(l) ?? '0';
      if (compareDecimal(a, remaining) > 0) {
        return this.createError({
          path,
          message: `At most ${formatMoney(remaining, invoice?.currency ?? '')} is still payable`,
        });
      }
      entered.push(a);
    }
    const total = entered.length === 0 ? '0' : sumDecimals(entered);
    const first = lines[0];
    if (isZeroDecimal(total)) {
      return first === undefined
        ? this.createError({ path: 'invoice_id', message: 'Nothing is payable on this invoice' })
        : this.createError({ path: `amounts.${first.id}`, message: 'Enter an amount on a line' });
    }
    if (compareDecimal(total, unallocated) > 0) {
      return this.createError({
        path: first === undefined ? 'invoice_id' : `amounts.${first.id}`,
        message: `The lines total more than the ${formatMoney(unallocated, invoice?.currency ?? '')} unallocated`,
      });
    }
    return true;
  });
}

function toAllocations(v: Values, invoice: InvoiceDto | null): LineAllocationIn[] | null {
  if (v.invoice_id === '') return null;
  return openLines(invoice)
    .map((l) => ({ line_id: l.id, amount: (v.amounts[l.id] ?? '').trim() }))
    .filter((a) => a.amount !== '' && DECIMAL.test(a.amount) && !isZeroDecimal(a.amount));
}

interface Props {
  payment: PaymentDto & { unallocated: string };
  onClose: () => void;
  onAllocated: (payment: PaymentDto) => void;
}

/**
 * Apply a verified payment's unallocated money (e.g. released by a void) to chosen invoice lines,
 * or, without an invoice, to the tenant's oldest open invoices. Lines are fulfilled when paid.
 */
export function AllocatePaymentDialog({ payment, onClose, onAllocated }: Props) {
  const keyFor = useIdempotencyKey();
  const [invoice, setInvoice] = useState<InvoiceDto | null>(null);
  const [initialValues] = useState<Values>({ invoice_id: '', amounts: {} });
  const search = useCallback(
    (q: string, signal: AbortSignal) => searchOpenInvoices(payment.tenant_id)(q, signal),
    [payment.tenant_id],
  );
  const lines = openLines(invoice);
  const money = (a: string) => <MoneyText amount={a} currency={payment.currency} />;

  return (
    <StepperFormDialog<Values>
      open
      title={`Allocate payment ${payment.reference}`}
      initialValues={initialValues}
      validationSchema={buildSchema(invoice, payment.unallocated)}
      submitLabel="Allocate"
      onClose={onClose}
      steps={[
        {
          label: 'Invoice',
          fields: ['invoice_id'],
          render: () => (
            <>
              <Alert severity="info">
                Unallocated: {formatMoney(payment.unallocated, payment.currency)}. Choose an invoice
                to allocate to specific lines, or leave it empty to fill the tenant&apos;s oldest
                open invoices.
              </Alert>
              <FormikAsyncIdAutocomplete<InvoiceDto>
                name="invoice_id"
                label="Invoice (optional)"
                fetchOptions={search}
                resolveOption={resolveInvoice}
                getOptionId={invoiceId}
                getOptionLabel={invoiceLabel}
                onOptionChange={setInvoice}
                noOptionsText="No open invoices"
              />
            </>
          ),
        },
        {
          label: 'Lines',
          fields: [],
          fieldsFor: (v) =>
            v.invoice_id === '' ? [] : ['invoice_id', ...lines.map((l) => `amounts.${l.id}`)],
          render: (f) =>
            f.values.invoice_id === '' ? (
              <Typography variant="body2">
                The money goes to the tenant&apos;s oldest open invoices, lines in order.
              </Typography>
            ) : (
              <Box className="flex flex-col gap-2">
                {lines.map((l) => (
                  <Box key={l.id} className="grid items-center gap-2 sm:grid-cols-[2fr_1fr]">
                    <Typography variant="body2">
                      {l.description} — payable {money(lineRemaining(l) ?? '0')}
                    </Typography>
                    <FormikTextField
                      name={`amounts.${l.id}`}
                      label={`Amount for line ${String(l.line_no)}`}
                      size="small"
                      slotProps={{ htmlInput: { inputMode: 'decimal' } }}
                    />
                  </Box>
                ))}
              </Box>
            ),
        },
      ]}
      renderReview={(v) => {
        const allocations = toAllocations(v, invoice);
        return (
          <KeyValueGrid
            columns={1}
            items={[
              {
                label: 'Applied to',
                value:
                  allocations === null
                    ? "The tenant's oldest open invoices"
                    : (invoice?.invoice_number ?? v.invoice_id),
              },
              ...(allocations ?? []).map((a) => ({
                label: lines.find((l) => l.id === a.line_id)?.description ?? a.line_id,
                value: isDecimalString(String(a.amount)) ? money(String(a.amount)) : a.amount,
              })),
            ]}
          />
        );
      }}
      onSubmit={async (v) => {
        const allocations = toAllocations(v, invoice);
        const body = allocations === null ? {} : { allocations };
        try {
          onAllocated(await platformPaymentService.allocate(payment.id, body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, {});
        }
      }}
    />
  );
}
