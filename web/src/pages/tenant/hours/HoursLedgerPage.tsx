import { Box, Chip, Link, Stack } from '@mui/material';
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
import { formatDate } from '../../../utils/dates';
import { formatInstantIn } from '../../../utils/time';
import { CustomerFilter, MachineFilter } from '../shared/financePickers';
import { PersonName } from '../shared/PersonName';
import { machineText, nameOr } from '../shared/names';
import { hoursText, LEDGER_TYPE_LABELS, LEDGER_TYPE_OPTIONS } from './hoursDisplay';

/** Append-only hours ledger: every activation, use, transfer, expiry and reversal (never edited). */
export function HoursLedgerPage() {
  const timeZone = useDisplayTimeZone();
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
      id: 'day',
      header: 'Day of use',
      render: (e) => (e.usage_day == null ? '—' : formatDate(e.usage_day)),
    },
    {
      id: 'hours',
      header: 'Hours',
      align: 'right',
      render: (e) => hoursText(e.signed_hours),
    },
    { id: 'customer', header: 'Customer', render: (e) => nameOr(e.customer_name, e.customer_id) },
    {
      id: 'machine',
      header: 'Machine',
      render: (e) => machineText(e.machine_code, e.machine_name, e.machine_id),
    },
    {
      id: 'purchase',
      header: 'Purchase',
      render: (e) => (
        <Link component={RouterLink} to={hoursPurchasePath(e.purchase_id)}>
          {nameOr(e.purchase_number, e.purchase_id)}
        </Link>
      ),
    },
    {
      id: 'job',
      header: 'Job',
      render: (e) =>
        e.job_id === null ? (
          '—'
        ) : (
          <Link component={RouterLink} to={jobDetailPath(e.job_id)}>
            {nameOr(e.job_number, e.job_id)}
          </Link>
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
        subtitle="Every change to customer hours, in order (provisional entries: hours drawn day by day while a job runs); balances are always derived from it"
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
