import { Box, Chip, Tab, Tabs, TextField } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import type { AllocationDayDto, WorkAllocationDto } from '../../../../api/allocationTypes';
import { allocationService } from '../../../../api/services/allocationService';
import type { CustomerDto, MachineDto } from '../../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { PageHeader } from '../../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { recordPath } from '../../../../navigation/recordRoutes';
import { initialFilter } from '../../../../navigation/urlFilters';
import { formatDate } from '../../../../utils/dates';
import { formatInstantIn } from '../../../../utils/time';
import { CustomerFilter, MachineFilter } from '../../shared/financePickers';
import { machineText } from '../../shared/names';
import { PersonName } from '../../shared/PersonName';
import { allocationTarget, KIND_OPTIONS, STATUS_OPTIONS } from './allocationDisplay';
import { AllocationStatusChip, KindChip, LotsList } from './allocationKit';
import { ReconciliationTab } from './ReconciliationTab';

const isDay = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v);

interface PinnedMachine {
  id: string;
  label: string;
}

/** Every engine hour by day: the ledger of allocations, and each machine-day's reconciliation. */
export function WorkAllocationsPage() {
  const navigate = useNavigate();
  const timeZone = useDisplayTimeZone();
  const [params] = useSearchParams();
  const [tab, setTab] = useState(params.get('tab') === 'days' ? 'days' : 'ledger');
  const [status, setStatus] = useState(() =>
    initialFilter(params, 'status', STATUS_OPTIONS, 'ACTIVE'),
  );
  const [kind, setKind] = useState(() => initialFilter(params, 'kind', KIND_OPTIONS, ''));
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [pinned, setPinned] = useState<PinnedMachine | null>(() => {
    const id = params.get('machine_id');
    return id === null ? null : { id, label: 'One machine' };
  });
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [from, setFrom] = useState(() => params.get('from') ?? '');
  const [to, setTo] = useState(() => params.get('to') ?? '');
  const fetchPage = useCallback<FetchPage<WorkAllocationDto>>(
    (query, signal) => allocationService.list(query, signal),
    [],
  );
  const openDay = (d: AllocationDayDto) => {
    setPinned({
      id: d.machine_id,
      label: machineText(d.machine_code, d.machine_name, d.machine_id),
    });
    setMachine(null);
    setFrom(d.day);
    setTo(d.day);
    setTab('ledger');
  };
  const open = (a: WorkAllocationDto) => {
    void navigate(
      a.status === 'PROPOSED' && a.correction_group_id !== null
        ? recordPath('WORK_ALLOCATION_CORRECTION', a.correction_group_id)
        : recordPath('WORK_ALLOCATION', a.id),
    );
  };
  const columns: DataColumn<WorkAllocationDto>[] = [
    { id: 'day', header: 'Work date', render: (a) => formatDate(a.work_date) },
    {
      id: 'machine',
      header: 'Machine',
      render: (a) => machineText(a.machine_code, a.machine_name, a.machine_id),
    },
    {
      id: 'range',
      header: 'Readings',
      render: (a) => (
        <span
          title={`${formatInstantIn(a.start_at, timeZone)} → ${formatInstantIn(a.end_at, timeZone)}`}
        >
          <span className="font-mono">
            {a.start_reading} → {a.end_reading}
          </span>
        </span>
      ),
    },
    {
      id: 'hours',
      header: 'Hours',
      align: 'right',
      render: (a) => <span className="font-mono">{a.hours}</span>,
    },
    { id: 'kind', header: 'Kind', render: (a) => <KindChip kind={a.kind} /> },
    { id: 'for', header: 'For', render: allocationTarget },
    { id: 'lots', header: 'Lots', render: (a) => <LotsList lots={a.lots} /> },
    { id: 'status', header: 'Status', render: (a) => <AllocationStatusChip status={a.status} /> },
    {
      id: 'by',
      header: 'Recorded by',
      render: (a) => <PersonName userId={a.recorded_by} name={a.recorded_by_name} />,
    },
  ];
  return (
    <>
      <PageHeader
        title="Work allocations"
        subtitle="Every engine hour by machine and day: customer work, authorized activity or unexplained"
      />
      <Tabs
        value={tab}
        onChange={(_e, v: string) => {
          setTab(v);
        }}
        aria-label="Work allocation views"
        sx={{ mb: 2 }}
      >
        <Tab value="ledger" label="Ledger" />
        <Tab value="days" label="Per-day reconciliation" />
      </Tabs>
      {tab === 'days' ? (
        <ReconciliationTab onOpenDay={openDay} />
      ) : (
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(a) => a.id}
          searchPlaceholder="Search machine code or name"
          filters={{
            status: status || undefined,
            kind: kind || undefined,
            machine_id: machine?.id ?? pinned?.id,
            customer_id: customer?.id,
            from: isDay(from) ? from : undefined,
            to: isDay(to) ? to : undefined,
          }}
          emptyTitle="No allocations"
          emptyDescription="Allocations are written from the readings as they arrive."
          isRowMuted={(a) => a.status === 'SUPERSEDED' || a.status === 'REJECTED'}
          onRowClick={open}
          toolbar={
            <Box className="flex flex-1 flex-col gap-2">
              <Box className="flex flex-wrap items-center gap-3">
                <Box className="flex flex-wrap gap-1" role="group" aria-label="Kind">
                  <Chip
                    size="small"
                    label="All kinds"
                    color={kind === '' ? 'primary' : 'default'}
                    variant={kind === '' ? 'filled' : 'outlined'}
                    onClick={() => {
                      setKind('');
                    }}
                  />
                  {KIND_OPTIONS.map((o) => (
                    <Chip
                      key={o.value}
                      size="small"
                      label={o.label}
                      color={kind === o.value ? 'primary' : 'default'}
                      variant={kind === o.value ? 'filled' : 'outlined'}
                      onClick={() => {
                        setKind(o.value);
                      }}
                    />
                  ))}
                </Box>
                <StaticSelectFilter
                  label="Status"
                  value={status}
                  options={STATUS_OPTIONS}
                  allLabel="Active (default)"
                  onChange={setStatus}
                />
              </Box>
              <Box className="flex flex-wrap items-center gap-3">
                {pinned !== null ? (
                  <Chip
                    label={`Machine: ${pinned.label}`}
                    onDelete={() => {
                      setPinned(null);
                    }}
                  />
                ) : (
                  <Box sx={{ minWidth: 240 }}>
                    <MachineFilter label="Machine" value={machine} onChange={setMachine} />
                  </Box>
                )}
                <Box sx={{ minWidth: 240 }}>
                  <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
                </Box>
                <TextField
                  size="small"
                  type="date"
                  label="From day"
                  value={from}
                  onChange={(e) => {
                    setFrom(e.target.value);
                  }}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <TextField
                  size="small"
                  type="date"
                  label="To day"
                  value={to}
                  onChange={(e) => {
                    setTo(e.target.value);
                  }}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
              </Box>
            </Box>
          }
        />
      )}
    </>
  );
}
