import { Box, Button, Chip } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router';
import { engineHoursService } from '../../../api/services/engineHoursService';
import type { MachineEngineHoursSummaryDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { engineHoursMachinePath, ROUTES } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import {
  RECONCILIATION_LABELS,
  RECONCILIATION_OPTIONS,
  RECONCILIATION_TONES,
} from './engineHoursDisplay';

/** Engine-hour reconciliation per machine: status, totals and open items (derived from readings). */
export function EngineHoursMachinesPage() {
  const timeZone = useDisplayTimeZone();
  const navigate = useNavigate();
  const [status, setStatus] = useState('');
  const fetchPage = useCallback<FetchPage<MachineEngineHoursSummaryDto>>(
    (query, signal) => engineHoursService.listMachines(query, signal),
    [],
  );
  const columns: DataColumn<MachineEngineHoursSummaryDto>[] = [
    {
      id: 'machine',
      header: 'Machine',
      render: (m) => (
        <span>
          <strong>{m.machine_code}</strong> · {m.machine_name}
        </span>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      render: (m) => (
        <StatusChip
          status={m.status}
          tones={RECONCILIATION_TONES}
          label={RECONCILIATION_LABELS[m.status]}
        />
      ),
    },
    {
      id: 'baseline',
      header: 'Baseline',
      render: (m) => (
        <Box className="flex flex-wrap items-center gap-1">
          <span className="font-mono">{m.baseline_reading ?? '—'}</span>
          {m.baseline_pending && <Chip size="small" variant="outlined" label="Awaiting decision" />}
        </Box>
      ),
    },
    {
      id: 'last',
      header: 'Last reading',
      render: (m) =>
        m.last_reading === null
          ? '—'
          : `${m.last_reading} · ${formatInstantIn(m.last_reading_at, timeZone)}`,
    },
    {
      id: 'total',
      header: 'Engine hours',
      align: 'right',
      render: (m) => <span className="font-mono">{m.totals.total_hours}</span>,
    },
    {
      id: 'customer',
      header: 'Customer work',
      align: 'right',
      render: (m) => <span className="font-mono">{m.totals.customer_work_hours}</span>,
    },
    {
      id: 'unexplained',
      header: 'Not yet explained',
      align: 'right',
      render: (m) => <span className="font-mono">{m.totals.unexplained_hours}</span>,
    },
    {
      id: 'open',
      header: 'Open items',
      align: 'right',
      render: (m) =>
        m.open_items === 0
          ? '0'
          : `${String(m.open_items)}${
              m.oldest_open_item_days === null
                ? ''
                : ` (oldest ${String(m.oldest_open_item_days)} d)`
            }`,
    },
  ];
  return (
    <>
      <PageHeader
        title="Engine-hour reconciliation"
        subtitle="Every engine hour of each machine accounted for: customer work, explained activity, or still to explain"
        actions={
          <Box className="flex flex-wrap gap-2">
            <Button
              component={RouterLink}
              to={ROUTES.tenantEngineHoursUnallocated}
              variant="outlined"
            >
              Hours to explain
            </Button>
            <Button component={RouterLink} to={ROUTES.tenantMeterBaselines} variant="outlined">
              Baselines
            </Button>
          </Box>
        }
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(m) => m.machine_id}
        searchPlaceholder="Search machine code or name"
        filters={{ status: status || undefined }}
        emptyTitle="No machines match"
        onRowClick={(m) => {
          void navigate(engineHoursMachinePath(m.machine_id));
        }}
        toolbar={
          <StaticSelectFilter
            label="Status"
            value={status}
            options={RECONCILIATION_OPTIONS}
            allLabel="All statuses"
            onChange={setStatus}
            minWidth={220}
          />
        }
      />
    </>
  );
}
