import Add from '@mui/icons-material/Add';
import { Button } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import type { InvoiceDto, InvoiceStatus } from '../../../api/types';
import { ExportMenu } from '../../../components/data/ExportMenu';
import { ServerDataTable } from '../../../components/data/ServerDataTable';
import { PageHeader } from '../../../components/feedback/PageHeader';
import type { SelectOption } from '../../../components/forms/FormikSelectField';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { platformInvoiceDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { RaiseInvoiceDialog } from '../raiseInvoice/RaiseInvoiceDialog';
import { INVOICE_COLUMNS, useInvoicePageFetcher } from './invoiceList';
import { InvoiceStatusFilter } from './InvoiceStatusFilter';

const KIND_OPTIONS: readonly SelectOption[] = [
  { value: 'SUBSCRIPTION', label: 'Subscription' },
  { value: 'AD_HOC', label: 'Ad hoc' },
];

/**
 * Platform invoices across tenants: scheduled subscription invoices and ad-hoc invoices raised at
 * any time (server paging, status and kind filters). Rows open the invoice details page.
 */
export function InvoicesPage() {
  const [status, setStatus] = useState<InvoiceStatus | ''>('');
  const [kind, setKind] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [raising, setRaising] = useState(false);
  const navigate = useNavigate();
  const notify = useNotify();
  const fetchPage = useInvoicePageFetcher();
  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  useLiveRefresh([ENTITY.platformInvoice, ENTITY.platformPayment], reload);
  const filters = useMemo(
    () => ({ status: status === '' ? undefined : status, kind: kind === '' ? undefined : kind }),
    [status, kind],
  );
  return (
    <>
      <PageHeader
        title="Invoices"
        subtitle="Subscription and ad-hoc invoices issued to tenants"
        actions={
          <>
            <ExportMenu reports={[{ code: 'subscription', filters }]} />
            <Can permission={PERMISSIONS.platformInvoiceRaise}>
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={() => {
                  setRaising(true);
                }}
              >
                Raise invoice
              </Button>
            </Can>
          </>
        }
      />
      <ServerDataTable<InvoiceDto>
        columns={INVOICE_COLUMNS}
        fetchPage={fetchPage}
        getRowId={(i) => i.id ?? `${i.tenant_id}-${i.period_start}`}
        filters={filters}
        searchable={false}
        toolbar={
          <>
            <InvoiceStatusFilter value={status} onChange={setStatus} />
            <StaticSelectFilter
              label="Kind"
              value={kind}
              options={KIND_OPTIONS}
              onChange={setKind}
              allLabel="All kinds"
            />
          </>
        }
        emptyTitle="No invoices"
        reloadKey={reloadKey}
        onRowClick={(i) => {
          if (i.id !== null) void navigate(platformInvoiceDetailPath(i.id));
        }}
      />
      {raising && (
        <RaiseInvoiceDialog
          onClose={() => {
            setRaising(false);
          }}
          onRaised={(inv) => {
            notify.success(`Invoice ${inv.invoice_number ?? ''} raised.`);
            reload();
            if (inv.id !== null) void navigate(platformInvoiceDetailPath(inv.id));
          }}
        />
      )}
    </>
  );
}
