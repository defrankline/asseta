import { Alert, Box, TextField } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { revenueService } from '../../../api/services/revenueService';
import type { MachineDto, RevenueDifferenceDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { MoneyText } from '../../../components/display/MoneyText';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { recordPath } from '../../../navigation/recordRoutes';
import { initialFilter } from '../../../navigation/urlFilters';
import { MachineFilter } from '../shared/financePickers';
import { DIFFERENCE_STATUS_OPTIONS } from './revenueDisplay';
import { differenceMachine, differencePeriod } from './revenueDisplay';
import { differenceChip, useDifferenceKit } from './revenueKits';

const isDay = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v);

/** Machine-periods whose engine hours did not turn into the expected money (beyond tolerance). */
export function RevenueDifferencesPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [status, setStatus] = useState(() =>
    initialFilter(params, 'status', DIFFERENCE_STATUS_OPTIONS, 'OPEN'),
  );
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const kit = useDifferenceKit(() => {
    setReloadKey((k) => k + 1);
  });
  const fetchPage = useCallback<FetchPage<RevenueDifferenceDto>>(
    (query, signal) => revenueService.listDifferences(query, signal),
    [],
  );
  const open = (d: RevenueDifferenceDto) => {
    void navigate(recordPath('REVENUE_DIFFERENCE', d.id));
  };
  const badRange = isDay(from) && isDay(to) && from > to;
  const columns: DataColumn<RevenueDifferenceDto>[] = [
    { id: 'machine', header: 'Machine', render: differenceMachine },
    { id: 'period', header: 'Period', render: differencePeriod },
    {
      id: 'expected',
      header: 'Expected',
      align: 'right',
      render: (d) => <MoneyText amount={d.expected_amount} currency={d.currency} />,
    },
    {
      id: 'attributed',
      header: 'Attributed',
      align: 'right',
      render: (d) => <MoneyText amount={d.attributed_amount} currency={d.currency} />,
    },
    {
      id: 'difference',
      header: 'Difference',
      align: 'right',
      render: (d) => (
        <MoneyText amount={d.adjusted_difference ?? d.difference} currency={d.currency} strong />
      ),
    },
    { id: 'reason', header: 'Reason', render: (d) => d.reason_name ?? '—' },
    { id: 'status', header: 'Status', render: differenceChip },
    { id: 'decide', header: '', align: 'right', render: kit.decideCell },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (d) => (
        <RowActionsMenu
          label={`difference of ${differenceMachine(d)}`}
          actions={[
            {
              key: 'view',
              label: 'View details',
              onClick: () => {
                open(d);
              },
            },
            ...kit.actionsFor(d).filter((a) => a.key !== 'decide'),
          ]}
        />
      ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Revenue differences"
        subtitle="Engine hours that did not turn into the expected money: differences to explain"
      />
      {badRange && <Alert severity="error">The “from” day must not be after the “to” day.</Alert>}
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(d) => d.id}
        searchPlaceholder="Search machine code or name"
        reloadKey={reloadKey}
        filters={{
          status: status || undefined,
          machine_id: machine?.id,
          day_from: isDay(from) && !badRange ? from : undefined,
          day_to: isDay(to) && !badRange ? to : undefined,
        }}
        emptyTitle={status === 'OPEN' ? 'No differences to explain' : 'No revenue differences'}
        isRowMuted={(d) => d.status === 'CLEARED'}
        onRowClick={open}
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={DIFFERENCE_STATUS_OPTIONS}
              allLabel="All statuses"
              onChange={setStatus}
              minWidth={240}
            />
            <Box sx={{ minWidth: 240 }}>
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
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
        }
      />
      {kit.dialog}
    </>
  );
}
