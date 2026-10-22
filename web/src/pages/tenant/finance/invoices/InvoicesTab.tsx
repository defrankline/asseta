import Add from '@mui/icons-material/Add';
import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { CanMutate } from '../../../../access/CanMutate';
import { hireInvoiceService } from '../../../../api/services/financeService';
import type { CustomerDto, HireInvoiceDto } from '../../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { hireInvoiceDetailPath } from '../../../../navigation/routes';
import { useNotify } from '../../../../notifications/useNotify';
import { formatDate } from '../../../../utils/dates';
import { formatInstantIn } from '../../../../utils/time';
import { INVOICE_STATUS_OPTIONS } from '../../shared/financeDisplay';
import { CustomerFilter } from '../../shared/financePickers';
import { useCustomerLabels } from '../../shared/useFinanceLabels';
import { CreateInvoiceDialog } from './CreateInvoiceDialog';
import { InvoiceStatusChips } from './InvoiceViews';
import { invoiceTitle } from './invoiceData';
import { useInvoiceActions } from './useInvoiceActions';
import { ENTITY } from '../../../../realtime/entities';
import { useLiveRefresh } from '../../../../realtime/hooks';

/** Tenant customer hire invoices (separate from platform subscription invoices). */
export function InvoicesTab({ timeZone }: { timeZone: string }) {
  const navigate = useNavigate();
  const notify = useNotify();
  const customerLabel = useCustomerLabels();
  const [status, setStatus] = useState('');
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [creating, setCreating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const liveReload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  useLiveRefresh([ENTITY.hireInvoice, ENTITY.customerPayment], liveReload);
  const reload = () => {
    setReloadKey((k) => k + 1);
  };
  const { actionsFor, dialogs } = useInvoiceActions({ onChanged: reload });
  const fetchPage = useCallback<FetchPage<HireInvoiceDto>>(
    (query, signal) => hireInvoiceService.list(query, signal),
    [],
  );
  const columns: DataColumn<HireInvoiceDto>[] = [
    { id: 'number', header: 'Invoice', render: (i) => <strong>{invoiceTitle(i)}</strong> },
    { id: 'customer', header: 'Customer', render: (i) => customerLabel(i.customer_id) },
    { id: 'status', header: 'Status', render: (i) => <InvoiceStatusChips invoice={i} /> },
    {
      id: 'total',
      header: 'Total',
      align: 'right',
      render: (i) => <MoneyText amount={i.total} currency={i.currency} />,
    },
    {
      id: 'balance',
      header: 'Balance (verified)',
      align: 'right',
      render: (i) =>
        i.status === 'ISSUED' ? <MoneyText amount={i.balance} currency={i.currency} /> : '—',
    },
    {
      id: 'issued',
      header: 'Issued',
      render: (i) => (i.issued_at === null ? '—' : formatInstantIn(i.issued_at, timeZone)),
    },
    { id: 'due', header: 'Due', render: (i) => formatDate(i.due_date) },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (i) => <RowActionsMenu label={invoiceTitle(i)} actions={actionsFor(i)} />,
    },
  ];
  return (
    <>
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(i) => i.id}
        filters={{ status: status || undefined, customer_id: customer?.id }}
        searchPlaceholder="Search invoice number"
        reloadKey={reloadKey}
        emptyTitle="No hire invoices"
        emptyDescription="Draft an invoice from a customer’s completed, billing-ready jobs."
        isRowMuted={(i) => i.status === 'VOIDED'}
        onRowClick={(i) => {
          void navigate(hireInvoiceDetailPath(i.id));
        }}
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={INVOICE_STATUS_OPTIONS}
              onChange={setStatus}
            />
            <Box sx={{ minWidth: 240 }}>
              <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
            </Box>
            <Box className="flex-1" />
            <CanMutate permission={PERMISSIONS.tenantFinanceInvoice}>
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={() => {
                  setCreating(true);
                }}
              >
                New invoice
              </Button>
            </CanMutate>
          </Box>
        }
      />
      {creating && (
        <CreateInvoiceDialog
          onClose={() => {
            setCreating(false);
          }}
          onCreated={(inv) => {
            notify.success('Draft invoice created.');
            void navigate(hireInvoiceDetailPath(inv.id));
          }}
        />
      )}
      {dialogs}
    </>
  );
}
