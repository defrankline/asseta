import { Box, Button, Chip, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router';
import type { LedgerEntryDto } from '../../../api/hoursTypes';
import { hoursService } from '../../../api/services/hoursService';
import type { CustomerDto, MachineDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { hoursPurchasePath } from '../../../navigation/hoursRoutes';
import { jobDetailPath } from '../../../navigation/routes';
import { initialFilter } from '../../../navigation/urlFilters';
import { formatInstantIn } from '../../../utils/time';
import { CustomerFilter, MachineFilter } from '../shared/financePickers';
import { PersonName } from '../shared/PersonName';
import { useCustomerLabels } from '../shared/useFinanceLabels';
import { useMachineLabels } from '../shared/useMachineLabels';
import { hoursText, LEDGER_TYPE_LABELS, LEDGER_TYPE_OPTIONS } from './hoursDisplay';

/** Append-only hours ledger: every activation, use, transfer, expiry and reversal (never edited). */
export function HoursLedgerPage() {
  const timeZone = useDisplayTimeZone();
  const machineName = useMachineLabels();
  const customerName = useCustomerLabels();
  const [params, setParams] = useSearchParams();
  const purchaseId = params.get('purchase_id') ?? undefined;
  const jobId = params.get('job_id') ?? undefined;
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [entryType, setEntryType] = useState(() =>
    initialFilter(params, 'entry_type', LEDGER_TYPE_OPTIONS, ''),
  );
  const fetchPage = useCallback<FetchPage<LedgerEntryDto>>(
    (query, signal) => hoursService.listLedger(query, signal),
    [],
  );
  const clear = (key: string) => {
    const next = new URLSearchParams(params);
    next.delete(key);
    setParams(next);
  };
  const columns: DataColumn<LedgerEntryDto>[] = [
    {
      id: 'at',
      header: 'When',
      sortField: 'occurred_at',
      render: (e) => formatInstantIn(e.occurred_at, timeZone),
    },
    { id: 'type', header: 'Entry', render: (e) => LEDGER_TYPE_LABELS[e.entry_type] },
    {
      id: 'hours',
      header: 'Hours',
      align: 'right',
      render: (e) => hoursText(e.signed_hours),
    },
    { id: 'customer', header: 'Customer', render: (e) => customerName(e.customer_id) },
    { id: 'machine', header: 'Machine', render: (e) => machineName(e.machine_id) },
    {
      id: 'purchase',
      header: 'Purchase',
      render: (e) => (
        <Button component={RouterLink} to={hoursPurchasePath(e.purchase_id)} size="small">
          Open
        </Button>
      ),
    },
    {
      id: 'job',
      header: 'Job',
      render: (e) =>
        e.job_id === null ? (
          '—'
        ) : (
          <Button component={RouterLink} to={jobDetailPath(e.job_id)} size="small">
            Open job
          </Button>
        ),
    },
    {
      id: 'source',
      header: 'Source',
      render: (e) =>
        e.activation_source === null
          ? '—'
          : e.activation_source === 'CREDIT'
            ? 'Credit'
            : 'Verified payment',
    },
    { id: 'reason', header: 'Reason', render: (e) => e.reason ?? '—' },
    { id: 'by', header: 'By', render: (e) => <PersonName userId={e.created_by} empty="System" /> },
  ];
  return (
    <>
      <PageHeader
        title="Hours ledger"
        subtitle="Every change to customer hours, in order; balances are always derived from it"
      />
      <Stack spacing={2}>
        {(purchaseId !== undefined || jobId !== undefined) && (
          <Box className="flex flex-wrap gap-2">
            {purchaseId !== undefined && (
              <Chip
                label="One purchase"
                onDelete={() => {
                  clear('purchase_id');
                }}
              />
            )}
            {jobId !== undefined && (
              <Chip
                label="One job"
                onDelete={() => {
                  clear('job_id');
                }}
              />
            )}
          </Box>
        )}
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(e) => e.id}
          searchable={false}
          initialSort="-occurred_at"
          filters={{
            purchase_id: purchaseId,
            job_id: jobId,
            customer_id: customer?.id,
            machine_id: machine?.id,
            entry_type: entryType === '' ? undefined : entryType,
          }}
          emptyTitle="No ledger entries"
          toolbar={
            <Box className="flex flex-wrap gap-3">
              <Box sx={{ minWidth: 240 }}>
                <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
              </Box>
              <Box sx={{ minWidth: 220 }}>
                <MachineFilter label="Machine" value={machine} onChange={setMachine} />
              </Box>
              <StaticSelectFilter
                label="Entry"
                value={entryType}
                options={LEDGER_TYPE_OPTIONS}
                allLabel="All entries"
                onChange={setEntryType}
              />
            </Box>
          }
        />
      </Stack>
    </>
  );
}
