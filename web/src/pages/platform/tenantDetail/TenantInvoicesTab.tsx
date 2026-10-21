import { Box, Button } from '@mui/material';
import { useMemo, useState } from 'react';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import type { InvoiceDto, InvoiceStatus } from '../../../api/types';
import { ServerDataTable } from '../../../components/data/ServerDataTable';
import { useNotify } from '../../../notifications/useNotify';
import { InvoiceDetailDialog } from '../invoices/InvoiceDetailDialog';
import { INVOICE_COLUMNS, useInvoicePageFetcher } from '../invoices/invoiceList';
import { InvoiceStatusFilter } from '../invoices/InvoiceStatusFilter';
import { GenerateInvoicesDialog } from './GenerateInvoicesDialog';
import { InvoicePreviewDialog } from './InvoicePreviewDialog';

interface TenantInvoicesTabProps {
  tenantId: string;
  subscriptionId: string;
}

type Open = 'preview' | 'generate' | null;

export function TenantInvoicesTab({ tenantId, subscriptionId }: TenantInvoicesTabProps) {
  const notify = useNotify();
  const [open, setOpen] = useState<Open>(null);
  const [status, setStatus] = useState<InvoiceStatus | ''>('');
  const [selected, setSelected] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useInvoicePageFetcher(tenantId);
  const filters = useMemo(() => ({ status: status === '' ? undefined : status }), [status]);
  const reload = () => {
    setReloadKey((k) => k + 1);
  };

  return (
    <Box>
      <ServerDataTable<InvoiceDto>
        columns={INVOICE_COLUMNS}
        fetchPage={fetchPage}
        getRowId={(i) => i.id ?? `${i.tenant_id}-${i.period_start}`}
        filters={filters}
        searchable={false}
        reloadKey={reloadKey}
        emptyTitle="No invoices for this tenant"
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center justify-between gap-2">
            <InvoiceStatusFilter value={status} onChange={setStatus} />
            <Box className="flex gap-2">
              <Button
                variant="outlined"
                onClick={() => {
                  setOpen('preview');
                }}
              >
                Preview next invoice
              </Button>
              <Can permission={PERMISSIONS.platformInvoiceGenerate}>
                <Button
                  variant="contained"
                  onClick={() => {
                    setOpen('generate');
                  }}
                >
                  Generate due invoices
                </Button>
              </Can>
            </Box>
          </Box>
        }
        onRowClick={(i) => {
          if (i.id !== null) setSelected(i.id);
        }}
      />
      {open === 'preview' && (
        <InvoicePreviewDialog
          subscriptionId={subscriptionId}
          onClose={() => {
            setOpen(null);
          }}
        />
      )}
      {open === 'generate' && (
        <GenerateInvoicesDialog
          subscriptionId={subscriptionId}
          onClose={() => {
            setOpen(null);
          }}
          onGenerated={(r) => {
            notify.success(
              `${String(r.created.length)} invoice(s) issued; ${String(r.existing_periods.length)} period(s) already invoiced.`,
            );
            reload();
          }}
        />
      )}
      {selected !== null && (
        <InvoiceDetailDialog
          invoiceId={selected}
          onClose={() => {
            setSelected(null);
          }}
          onChanged={reload}
        />
      )}
    </Box>
  );
}
