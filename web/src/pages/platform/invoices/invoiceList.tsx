import { useCallback } from 'react';
import { INVOICE_KINDS, INVOICE_STATUSES } from '../../../api/services/billingSchemas';
import { platformInvoiceService } from '../../../api/services/platformInvoiceService';
import type { InvoiceDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { formatDate } from '../../../utils/dates';
import { INVOICE_KIND_LABELS, INVOICE_KIND_TONES } from '../invoiceDetail/invoiceDisplay';
import { INVOICE_TONES } from '../shared/billingDisplay';

export const INVOICE_COLUMNS: DataColumn<InvoiceDto>[] = [
  { id: 'number', header: 'Invoice no.', render: (i) => i.invoice_number ?? '—' },
  {
    id: 'kind',
    header: 'Kind',
    render: (i) => (
      <StatusChip status={i.kind} tones={INVOICE_KIND_TONES} label={INVOICE_KIND_LABELS[i.kind]} />
    ),
  },
  {
    id: 'period',
    header: 'Period',
    render: (i) => `${formatDate(i.period_start)} – ${formatDate(i.period_end)}`,
  },
  { id: 'due', header: 'Due', render: (i) => formatDate(i.due_date) },
  {
    id: 'status',
    header: 'Status',
    render: (i) =>
      i.status !== null ? <StatusChip status={i.status} tones={INVOICE_TONES} /> : '—',
  },
  {
    id: 'total',
    header: 'Total',
    align: 'right',
    render: (i) => <MoneyText amount={i.total} currency={i.currency} />,
  },
  {
    id: 'balance',
    header: 'Balance',
    align: 'right',
    render: (i) => <MoneyText amount={i.balance} currency={i.currency} strong />,
  },
];

/** Server-paged invoice list fetcher, optionally scoped to one tenant. */
export function useInvoicePageFetcher(tenantId?: string) {
  return useCallback(
    (q: ServerQuery, signal: AbortSignal) => {
      const status = INVOICE_STATUSES.find((s) => s === q.filters.status);
      const kind = INVOICE_KINDS.find((k) => k === q.filters.kind);
      return platformInvoiceService.list(
        {
          page: q.page,
          page_size: q.page_size,
          ...(status !== undefined ? { status } : {}),
          ...(kind !== undefined ? { kind } : {}),
          ...(tenantId !== undefined ? { tenant_id: tenantId } : {}),
        },
        signal,
      );
    },
    [tenantId],
  );
}
