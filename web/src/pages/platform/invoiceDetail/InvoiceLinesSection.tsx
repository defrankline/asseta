import { Box, Typography } from '@mui/material';
import { useCallback } from 'react';
import { usePlatformInvoicingService } from '../../../api/services/platformInvoicingService';
import type { InvoiceDto, InvoiceLineDto, PaymentDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { DetailSection } from '../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { formatDate, formatInstant } from '../../../utils/dates';
import { humanize } from '../../../utils/text';
import { InvoiceTotals } from '../raiseInvoice/RaiseInvoiceReview';
import { optionLabel, PAYMENT_METHOD_OPTIONS, PAYMENT_TONES } from '../shared/billingDisplay';
import {
  FULFILMENT_LABELS,
  FULFILMENT_TONES,
  LINE_PAYMENT_TONES,
  lineFulfilment,
  linePaymentState,
} from './invoiceDisplay';

function lineColumns(invoice: InvoiceDto): DataColumn<InvoiceLineDto>[] {
  const money = (v: string | null | undefined) =>
    v == null ? '—' : <MoneyText amount={v} currency={invoice.currency} />;
  return [
    {
      id: 'item',
      header: 'Item',
      render: (l) => (
        <>
          <strong>{l.description}</strong>
          <Typography variant="caption" color="text.secondary" component="div">
            {humanize(l.line_type)}
            {l.service_from !== null && l.service_to !== null
              ? ` · ${formatDate(l.service_from)} – ${formatDate(l.service_to)}`
              : ''}
            {l.sms_credits != null ? ` · ${l.sms_credits.toLocaleString('en-US')} SMS credits` : ''}
          </Typography>
        </>
      ),
    },
    { id: 'qty', header: 'Qty', align: 'right', render: (l) => l.quantity },
    { id: 'unit', header: 'Unit price', align: 'right', render: (l) => money(l.unit_price) },
    { id: 'amount', header: 'Amount', align: 'right', render: (l) => money(l.amount) },
    { id: 'payable', header: 'Payable', align: 'right', render: (l) => money(l.payable) },
    { id: 'paid', header: 'Paid', align: 'right', render: (l) => money(l.paid) },
    {
      id: 'payment',
      header: 'Payment',
      render: (l) => {
        const state = linePaymentState(l);
        return state === null ? '—' : <StatusChip status={state} tones={LINE_PAYMENT_TONES} />;
      },
    },
    {
      id: 'fulfilment',
      header: 'Fulfilment',
      render: (l) => {
        const f = lineFulfilment(invoice, l);
        return f === null ? (
          '—'
        ) : (
          <StatusChip status={f} tones={FULFILMENT_TONES} label={FULFILMENT_LABELS[f]} />
        );
      },
    },
  ];
}

/** Lines with payable, paid, payment state and fulfilment in its area; server totals. */
export function InvoiceLinesSection({ invoice }: { invoice: InvoiceDto }) {
  return (
    <DetailSection title="Lines">
      <StaticTable
        ariaLabel="Invoice lines"
        columns={lineColumns(invoice)}
        rows={invoice.lines}
        getRowId={(l) => String(l.line_no)}
      />
      <Box className="mt-3">
        <InvoiceTotals invoice={invoice} />
      </Box>
    </DetailSection>
  );
}

/** Payments that touch this invoice, and how much of each went to which line. */
export function PaymentAllocationsSection({
  invoice,
  reloadKey = 0,
}: {
  invoice: InvoiceDto & { id: string };
  reloadKey?: number;
}) {
  const service = usePlatformInvoicingService();
  const load = useCallback(
    async (signal: AbortSignal) =>
      (await service.listTenantPayments(invoice.tenant_id, signal)).filter(
        (p) =>
          p.invoice_id === invoice.id || p.allocations.some((a) => a.invoice_id === invoice.id),
      ),
    [service, invoice.tenant_id, invoice.id],
  );
  const payments = useAsyncResource(load, [reloadKey]);
  const lineName = new Map(invoice.lines.map((l) => [l.id ?? '', l.description]));
  const columns: DataColumn<PaymentDto>[] = [
    {
      id: 'ref',
      header: 'Payment',
      render: (p) => (
        <>
          <strong>{p.reference}</strong>
          <Typography variant="caption" color="text.secondary" component="div">
            {optionLabel(PAYMENT_METHOD_OPTIONS, p.method)} · received {formatDate(p.received_on)}
          </Typography>
        </>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      render: (p) => <StatusChip status={p.status} tones={PAYMENT_TONES} />,
    },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (p) => <MoneyText amount={p.amount} currency={p.currency} />,
    },
    {
      id: 'allocations',
      header: 'Applied to this invoice',
      render: (p) => {
        const rows = p.allocations.filter((a) => a.invoice_id === invoice.id);
        if (rows.length === 0) return p.status === 'VERIFIED' ? 'Nothing yet' : 'On verification';
        return (
          <Box component="ul" className="m-0 list-none p-0">
            {rows.map((a) => (
              <li key={a.id} className={a.released_at !== null ? 'line-through opacity-70' : ''}>
                {a.line_id === null
                  ? 'Whole invoice (lines in order)'
                  : (lineName.get(a.line_id) ?? 'Line')}
                : <MoneyText amount={a.amount} currency={p.currency} />
                {a.released_at !== null &&
                  ` — released ${formatInstant(a.released_at)}${a.release_reason !== null ? ` (${a.release_reason})` : ''}`}
              </li>
            ))}
          </Box>
        );
      },
    },
  ];
  return (
    <DetailSection title="Payments and line allocation">
      <AsyncContent
        resource={payments}
        isEmpty={(rows) => rows.length === 0}
        emptyTitle="No payments applied to this invoice"
        errorTitle="Could not load payments"
      >
        {(rows) => (
          <StaticTable ariaLabel="Payments" columns={columns} rows={rows} getRowId={(p) => p.id} />
        )}
      </AsyncContent>
    </DetailSection>
  );
}
