import { Box, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import type { CreditInvoiceDto } from '../../../../api/hoursTypes';
import { creditInvoiceService } from '../../../../api/services/creditInvoiceService';
import type { CustomerDto } from '../../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { MoneyText } from '../../../../components/display/MoneyText';
import { PageHeader } from '../../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { creditInvoicePath } from '../../../../navigation/hoursRoutes';
import { initialFilter } from '../../../../navigation/urlFilters';
import { CustomerFilter } from '../../shared/financePickers';
import { machineText, nameOr } from '../../shared/names';
import { urlPeriod } from '../../shared/urlPeriod';
import { UrlPeriodChip } from '../../shared/UrlPeriodChip';
import { HoursOffNotice } from '../HoursDialogs';
import { hoursText } from '../hoursDisplay';
import { useHoursPolicy } from '../useHoursPolicy';
import { CreditInvoiceStatus } from './CreditInvoiceParts';
import { CREDIT_INVOICE_STATUS_OPTIONS, OVERDUE_OPTIONS } from './creditInvoiceDisplay';

/** Credit invoices: the credit part of each order, with what is paid, the balance and the due date. */
export function CreditInvoicesPage() {
  const navigate = useNavigate();
  const hours = useHoursPolicy();
  const [params, setParams] = useSearchParams();
  const { dateFrom, dateTo } = urlPeriod(params);
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  // Opened from a customer's credit owed (`?customer_id=`) until another customer is chosen.
  const urlCustomer = params.get('customer_id') ?? undefined;
  const [status, setStatus] = useState(() =>
    initialFilter(params, 'status', CREDIT_INVOICE_STATUS_OPTIONS, ''),
  );
  const [overdue, setOverdue] = useState(() =>
    initialFilter(params, 'overdue', OVERDUE_OPTIONS, ''),
  );
  const fetchPage = useCallback<FetchPage<CreditInvoiceDto>>(
    (query, signal) => creditInvoiceService.list(query, signal),
    [],
  );
  const columns: DataColumn<CreditInvoiceDto>[] = [
    { id: 'number', header: 'Invoice', render: (i) => <strong>{i.invoice_number}</strong> },
    { id: 'customer', header: 'Customer', render: (i) => nameOr(i.customer_name, i.customer_id) },
    { id: 'order', header: 'Order', render: (i) => i.purchase_number ?? '—' },
    {
      id: 'machine',
      header: 'Machine',
      render: (i) => machineText(i.machine_code, i.machine_name, i.machine_id),
    },
    { id: 'hours', header: 'Hours', align: 'right', render: (i) => hoursText(i.hours) },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (i) => <MoneyText amount={i.amount} currency={i.currency} />,
    },
    {
      id: 'paid',
      header: 'Paid',
      align: 'right',
      render: (i) => <MoneyText amount={i.paid} currency={i.currency} />,
    },
    {
      id: 'balance',
      header: 'Balance',
      align: 'right',
      render: (i) => <MoneyText amount={i.balance} currency={i.currency} strong />,
    },
    { id: 'due', header: 'Due', sortField: 'due_date', render: (i) => i.due_date },
    { id: 'status', header: 'Status', render: (i) => <CreditInvoiceStatus invoice={i} /> },
  ];
  return (
    <>
      <PageHeader
        title="Credit invoices"
        subtitle="The credit part of each order: paid in full or in parts by cash, bank or mobile money"
      />
      <Stack spacing={2}>
        <HoursOffNotice off={hours.status === 'known' && !hours.on} />
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(i) => i.id}
          searchPlaceholder="Search invoice, order or customer"
          initialSort="due_date"
          filters={{
            customer_id: customer?.id ?? urlCustomer,
            status: status === '' ? undefined : status,
            overdue: overdue === '' ? undefined : overdue,
            date_from: dateFrom,
            date_to: dateTo,
          }}
          emptyTitle="No credit invoices"
          emptyDescription="An invoice is created when an order is recorded with a credit part."
          isRowMuted={(i) => i.status === 'CANCELLED' || i.status === 'PAID'}
          onRowClick={(i) => {
            void navigate(creditInvoicePath(i.id));
          }}
          toolbar={
            <Box className="flex flex-wrap items-center gap-2">
              <Box sx={{ minWidth: 220 }}>
                <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
              </Box>
              <StaticSelectFilter
                label="Status"
                value={status}
                options={CREDIT_INVOICE_STATUS_OPTIONS}
                allLabel="All statuses"
                onChange={setStatus}
              />
              <StaticSelectFilter
                label="Overdue"
                value={overdue}
                options={OVERDUE_OPTIONS}
                allLabel="All invoices"
                onChange={setOverdue}
              />
              <UrlPeriodChip params={params} setParams={setParams} />
            </Box>
          }
        />
      </Stack>
    </>
  );
}
