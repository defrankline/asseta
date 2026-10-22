import { Box, Stack, Typography } from '@mui/material';
import { useCallback } from 'react';
import { newIdempotencyKey } from '../../../api/ids';
import { withErrorCode } from '../../../api/lifecycle';
import { usePlatformInvoicingService } from '../../../api/services/platformInvoicingService';
import type { AdHocInvoiceIn, InvoiceDto, InvoiceLineDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { formatDate } from '../../../utils/dates';
import { humanize } from '../../../utils/text';
import { RAISE_ERROR_HINTS, toRaiseBody, type RaiseInvoiceValues } from './raiseInvoiceForm';

interface RaiseInvoiceReviewProps {
  values: RaiseInvoiceValues;
  tenantName: string | null;
}

function servicePeriod(l: InvoiceLineDto): string {
  return l.service_from !== null && l.service_to !== null
    ? ` · ${formatDate(l.service_from)} – ${formatDate(l.service_to)}`
    : '';
}

function lineColumns(currency: string): DataColumn<InvoiceLineDto>[] {
  const money = (v: string) => <MoneyText amount={v} currency={currency} />;
  return [
    {
      id: 'item',
      header: 'Item',
      render: (l) => (
        <>
          <strong>{l.description}</strong>
          <Typography variant="caption" color="text.secondary" component="div">
            {humanize(l.line_type)}
            {servicePeriod(l)}
          </Typography>
        </>
      ),
    },
    { id: 'qty', header: 'Qty', align: 'right', render: (l) => l.quantity },
    { id: 'unit', header: 'Unit price', align: 'right', render: (l) => money(l.unit_price) },
    { id: 'amount', header: 'Amount', align: 'right', render: (l) => money(l.amount) },
  ];
}

type Totals = Pick<InvoiceDto, 'currency' | 'subtotal' | 'discount_total' | 'tax_total' | 'total'>;

/** Totals block; every figure comes from the server (never summed in the browser). */
export function InvoiceTotals({ invoice }: { invoice: Totals }) {
  const rows: [string, string][] = [
    ['Subtotal', invoice.subtotal],
    ['Discounts', invoice.discount_total],
    ['Tax', invoice.tax_total],
  ];
  return (
    <Box component="dl" className="ml-auto grid w-full max-w-xs grid-cols-2 gap-1" sx={{ m: 0 }}>
      {rows.map(([label, amount]) => (
        <Box key={label} className="contents">
          <Typography component="dt" variant="body2" color="text.secondary">
            {label}
          </Typography>
          <Typography component="dd" variant="body2" className="text-right" sx={{ m: 0 }}>
            <MoneyText amount={amount} currency={invoice.currency} />
          </Typography>
        </Box>
      ))}
      <Typography component="dt" variant="subtitle2">
        Total
      </Typography>
      <Typography component="dd" variant="subtitle2" className="text-right" sx={{ m: 0 }}>
        <MoneyText amount={invoice.total} currency={invoice.currency} strong />
      </Typography>
    </Box>
  );
}

export function InvoiceLinesTable({ invoice }: { invoice: InvoiceDto }) {
  return (
    <StaticTable
      ariaLabel="Invoice lines"
      columns={lineColumns(invoice.currency)}
      rows={invoice.lines}
      getRowId={(l) => String(l.line_no)}
    />
  );
}

/** Review step: terms plus the server-computed preview (lines, discounts, tax, totals). */
export function RaiseInvoiceReview({ values, tenantName }: RaiseInvoiceReviewProps) {
  const service = usePlatformInvoicingService();
  const bodyKey = JSON.stringify(toRaiseBody(values));
  const load = useCallback(
    // The preview saves nothing; every call is its own request.
    () =>
      service
        .previewInvoice(JSON.parse(bodyKey) as AdHocInvoiceIn, newIdempotencyKey())
        .catch((err: unknown) => {
          // e.g. PERIOD_ALREADY_BILLED: show the stable code and what to do about it.
          throw withErrorCode(err, RAISE_ERROR_HINTS);
        }),
    [service, bodyKey],
  );
  const preview = useAsyncResource(load);

  return (
    <AsyncContent
      resource={preview}
      loadingLabel="Calculating totals"
      errorTitle="The server refused this invoice"
    >
      {(p) => (
        <Stack spacing={2} aria-label="Invoice preview" role="region">
          <KeyValueGrid
            columns={3}
            items={[
              { label: 'Tenant', value: tenantName ?? values.tenant_id },
              { label: 'Currency', value: p.currency },
              { label: 'Due date', value: formatDate(p.due_date) },
              { label: 'Notes', value: values.notes.trim() === '' ? '—' : values.notes },
            ]}
          />
          <InvoiceLinesTable invoice={p} />
          <InvoiceTotals invoice={p} />
        </Stack>
      )}
    </AsyncContent>
  );
}
