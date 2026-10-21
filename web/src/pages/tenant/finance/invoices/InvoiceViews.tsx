import { Box, Table, TableBody, TableCell, TableRow, Typography } from '@mui/material';
import type { HireInvoiceDto, HireInvoiceLineDto } from '../../../../api/types';
import type { DataColumn } from '../../../../components/data/ServerDataTable';
import { StaticTable } from '../../../../components/data/StaticTable';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { humanize } from '../../../../utils/text';
import { invoiceTitle } from './invoiceData';
import { INVOICE_STATUS_TONES, PAYMENT_STATE_TONES } from '../../shared/financeDisplay';

/** Status plus, for issued invoices, the payment state (from verified allocations only). */
export function InvoiceStatusChips({ invoice: i }: { invoice: HireInvoiceDto }) {
  return (
    <Box component="span" className="inline-flex flex-wrap gap-1">
      <StatusChip status={i.status} tones={INVOICE_STATUS_TONES} />
      {i.payment_state !== null && (
        <StatusChip status={i.payment_state} tones={PAYMENT_STATE_TONES} />
      )}
    </Box>
  );
}

interface LinesProps {
  invoice: HireInvoiceDto;
  jobLabel: (jobId: string) => string;
  machineLabel: (machineId: string) => string;
}

/** Snapshot lines exactly as stored on the invoice (quantity / price / amount as sent). */
export function InvoiceLinesTable({ invoice, jobLabel, machineLabel }: LinesProps) {
  const cur = invoice.currency;
  const columns: DataColumn<HireInvoiceLineDto>[] = [
    { id: 'no', header: '#', render: (l) => l.line_no },
    { id: 'job', header: 'Job', render: (l) => jobLabel(l.job_id) },
    { id: 'machine', header: 'Machine', render: (l) => machineLabel(l.machine_id) },
    { id: 'kind', header: 'Kind', render: (l) => humanize(l.kind) },
    { id: 'desc', header: 'Description', render: (l) => l.description },
    { id: 'qty', header: 'Quantity', align: 'right', render: (l) => l.quantity },
    {
      id: 'price',
      header: 'Unit price',
      align: 'right',
      render: (l) => <MoneyText amount={l.unit_price} currency={cur} />,
    },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (l) => <MoneyText amount={l.amount} currency={cur} />,
    },
  ];
  return (
    <StaticTable
      ariaLabel="Invoice lines"
      columns={columns}
      rows={invoice.lines}
      getRowId={(l) => String(l.line_no)}
    />
  );
}

/** Server totals; paid and balance count VERIFIED payments only. */
export function InvoiceTotals({ invoice: i }: { invoice: HireInvoiceDto }) {
  const rows: [string, string, boolean][] = [
    ['Subtotal', i.subtotal, false],
    ['Discounts', i.discount_total, false],
    ['Tax', i.tax_total, false],
    ['Total', i.total, true],
  ];
  if (i.status === 'ISSUED') {
    rows.push(['Paid (verified)', i.amount_paid, false], ['Balance due', i.balance, true]);
  }
  return (
    <Box className="flex justify-end">
      <Table size="small" aria-label="Invoice totals" sx={{ width: 'auto', minWidth: 320 }}>
        <TableBody>
          {rows.map(([label, amount, strong]) => (
            <TableRow key={label}>
              <TableCell>
                <Typography variant="body2" sx={{ fontWeight: strong ? 600 : 400 }}>
                  {label}
                </Typography>
              </TableCell>
              <TableCell align="right">
                <MoneyText amount={amount} currency={i.currency} strong={strong} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}

/** What voiding does, in plain language (issued invoices are corrected by reversal, never edited). */
export function VoidExplanation({ invoice: i }: { invoice: HireInvoiceDto }) {
  return i.status === 'ISSUED' ? (
    <Box className="flex flex-col gap-1">
      <Typography variant="body2">
        Voiding <strong>{invoiceTitle(i)}</strong> records a reversal of{' '}
        <MoneyText amount={i.total} currency={i.currency} strong /> on the customer’s statement. The
        invoice itself is not changed or deleted.
      </Typography>
      <Typography variant="body2">
        Payments allocated to it are released back to the customer as unallocated credit, and its
        jobs become invoiceable again.
      </Typography>
    </Box>
  ) : (
    <Typography variant="body2">
      Discarding this draft releases its jobs so they can be invoiced again. Nothing was issued, so
      no reversal is recorded.
    </Typography>
  );
}
