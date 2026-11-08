import { Alert, Box, Chip, TextField, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import type { AllocationDayDto } from '../../../../api/allocationTypes';
import { allocationService } from '../../../../api/services/allocationService';
import type { MachineDto } from '../../../../api/types';
import type { DataColumn } from '../../../../components/data/ServerDataTable';
import { StaticTable } from '../../../../components/data/StaticTable';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { formatDate, todayIsoDate } from '../../../../utils/dates';
import { MachineFilter } from '../../shared/financePickers';
import { machineText } from '../../shared/names';
import { isNonZero } from './allocationDisplay';
import dayjs from 'dayjs';

const isDay = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v);
/** The server answers at most 93 days at a time. */
const MAX_DAYS = 93;

const hoursCell = (hours: string) => <span className="font-mono">{hours}</span>;

const columns: DataColumn<AllocationDayDto>[] = [
  { id: 'day', header: 'Day', render: (d) => formatDate(d.day) },
  {
    id: 'machine',
    header: 'Machine',
    render: (d) => machineText(d.machine_code, d.machine_name, d.machine_id),
  },
  {
    id: 'total',
    header: 'Total engine hours',
    align: 'right',
    render: (d) => hoursCell(d.total_engine_hours),
  },
  {
    id: 'customer',
    header: 'Customer',
    align: 'right',
    render: (d) => hoursCell(d.customer_hours),
  },
  {
    id: 'authorized',
    header: 'Authorized',
    align: 'right',
    render: (d) => hoursCell(d.authorized_hours),
  },
  {
    id: 'unexplained',
    header: 'Unexplained',
    align: 'right',
    render: (d) => hoursCell(d.unexplained_hours),
  },
  {
    id: 'difference',
    header: 'Difference',
    align: 'right',
    render: (d) =>
      d.reconciled && !isNonZero(d.difference_hours) ? (
        <Chip size="small" variant="outlined" color="success" label="Reconciled" />
      ) : (
        <Chip size="small" color="error" label={`Difference ${d.difference_hours} h`} />
      ),
  },
];

/** Per machine and day: total engine hours = customer + authorized + unexplained, the difference shown. */
export function ReconciliationTab({ onOpenDay }: { onOpenDay: (day: AllocationDayDto) => void }) {
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [from, setFrom] = useState(() => dayjs().subtract(6, 'day').format('YYYY-MM-DD'));
  const [to, setTo] = useState(todayIsoDate);
  const ready = isDay(from) && isDay(to);
  const span = ready ? dayjs(to).diff(dayjs(from), 'day') : 0;
  const rangeOk = ready && span >= 0 && span < MAX_DAYS;
  const load = useCallback(
    (signal: AbortSignal) =>
      allocationService.reconciliation({ from, to, machine_id: machine?.id }, signal),
    [from, to, machine?.id],
  );
  const days = useAsyncResource(load, [from, to, machine?.id], rangeOk);
  return (
    <Box className="flex flex-col gap-3">
      <Box className="flex flex-wrap items-center gap-3">
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
      <Typography variant="body2" color="text.secondary">
        Total engine hours = customer + authorized + unexplained. A difference is hours not yet
        allocated, such as a reading that went down with no approved reset.
      </Typography>
      {!rangeOk ? (
        <Alert severity="error">Choose a range of 1 to {MAX_DAYS} days.</Alert>
      ) : (
        <AsyncContent resource={days} errorTitle="Could not load the reconciliation">
          {(rows) =>
            rows.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No engine hours in these days.
              </Typography>
            ) : (
              <StaticTable
                ariaLabel="Per-day reconciliation"
                columns={columns}
                rows={rows}
                getRowId={(d) => `${d.machine_id}:${d.day}`}
                onRowClick={onOpenDay}
              />
            )
          }
        </AsyncContent>
      )}
    </Box>
  );
}
