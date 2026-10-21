import { useMemo, useState } from 'react';
import type { InvoiceDto, InvoiceStatus } from '../../../api/types';
import { ServerDataTable } from '../../../components/data/ServerDataTable';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { InvoiceDetailDialog } from './InvoiceDetailDialog';
import { INVOICE_COLUMNS, useInvoicePageFetcher } from './invoiceList';
import { InvoiceStatusFilter } from './InvoiceStatusFilter';

/** Platform invoices across tenants (server paging, status filter). */
export function InvoicesPage() {
  const [status, setStatus] = useState<InvoiceStatus | ''>('');
  const [selected, setSelected] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useInvoicePageFetcher();
  const filters = useMemo(() => ({ status: status === '' ? undefined : status }), [status]);
  return (
    <>
      <PageHeader title="Invoices" subtitle="Subscription invoices issued to tenants" />
      <ServerDataTable<InvoiceDto>
        columns={INVOICE_COLUMNS}
        fetchPage={fetchPage}
        getRowId={(i) => i.id ?? `${i.tenant_id}-${i.period_start}`}
        filters={filters}
        searchable={false}
        toolbar={<InvoiceStatusFilter value={status} onChange={setStatus} />}
        emptyTitle="No invoices"
        reloadKey={reloadKey}
        onRowClick={(i) => {
          if (i.id !== null) setSelected(i.id);
        }}
      />
      {selected !== null && (
        <InvoiceDetailDialog
          invoiceId={selected}
          onClose={() => {
            setSelected(null);
          }}
          onChanged={() => {
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
