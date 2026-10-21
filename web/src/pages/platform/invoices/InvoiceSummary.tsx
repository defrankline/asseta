import { Stack, Typography } from '@mui/material';
import type { InvoiceDto, InvoiceLineDto } from '../../../api/types';
import { StaticTable } from '../../../components/data/StaticTable';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { humanize } from '../../../utils/text';
import { formatDate } from '../../../utils/dates';
import { INVOICE_TONES } from '../shared/billingDisplay';

function lineColumns(currency: string): DataColumn<InvoiceLineDto>[] {
  return [
    { id: 'no', header: '#', render: (l) => l.line_no },
    { id: 'type', header: 'Type', render: (l) => humanize(l.line_type) },
    { id: 'description', header: 'Description', render: (l) => l.description },
    {
      id: 'service',
      header: 'Service period',
      render: (l) =>
        l.service_from === null
          ? '—'
          : `${formatDate(l.service_from)} – ${formatDate(l.service_to)}`,
    },
    { id: 'qty', header: 'Qty', align: 'right', render: (l) => l.quantity },
    {
      id: 'unit',
      header: 'Unit price',
      align: 'right',
      render: (l) => <MoneyText amount={l.unit_price} currency={currency} />,
    },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (l) => <MoneyText amount={l.amount} currency={currency} />,
    },
  ];
}

/** Invoice header, immutable lines and totals; used for issued invoices and previews. */
export function InvoiceSummary({ invoice: inv }: { invoice: InvoiceDto }) {
  const money = (amount: string, strong = false) => (
    <MoneyText amount={amount} currency={inv.currency} strong={strong} />
  );
  return (
    <Stack spacing={2}>
      <KeyValueGrid
        columns={4}
        items={[
          { label: 'Invoice no.', value: inv.invoice_number ?? 'Preview (not issued)' },
          {
            label: 'Status',
            value:
              inv.status !== null ? <StatusChip status={inv.status} tones={INVOICE_TONES} /> : '—',
          },
          {
            label: 'Period',
            value: `${formatDate(inv.period_start)} – ${formatDate(inv.period_end)}`,
          },
          { label: 'Due date', value: formatDate(inv.due_date) },
          {
            label: 'Billable / enrolled assets',
            value: `${String(inv.billable_assets)} / ${String(inv.enrolled_assets)}`,
          },
          { label: 'Currency', value: inv.currency },
        ]}
      />
      <Typography variant="subtitle2">Lines</Typography>
      {inv.lines.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No lines.
        </Typography>
      ) : (
        <StaticTable
          ariaLabel="Invoice lines"
          columns={lineColumns(inv.currency)}
          rows={inv.lines}
          getRowId={(l) => String(l.line_no)}
        />
      )}
      <KeyValueGrid
        columns={4}
        items={[
          { label: 'Subtotal', value: money(inv.subtotal) },
          { label: 'Discount', value: money(inv.discount_total) },
          { label: 'Tax', value: money(inv.tax_total) },
          { label: 'Total', value: money(inv.total, true) },
          { label: 'Paid (verified)', value: money(inv.amount_paid) },
          { label: 'Credits applied', value: money(inv.credits_applied) },
          { label: 'Balance', value: money(inv.balance, true) },
        ]}
      />
    </Stack>
  );
}
