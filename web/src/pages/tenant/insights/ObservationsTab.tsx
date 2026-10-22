import { Alert, Box, Link, Typography } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { tenantMlService } from '../../../api/services/insightsService';
import type { MachineDto, TenantPredictionDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { caseDetailPath, machineDetailPath } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import { MachinePicker } from '../shared/MachinePicker';
import { useMachineLabels } from '../shared/useMachineLabels';
import { OBSERVATIONS_NOTICE } from './insightsDisplay';

/** Surfaced model observations (`tenant.case.read`): neutral text and the case to review — no score. */
export function ObservationsTab({ timeZone }: { timeZone: string }) {
  const machineName = useMachineLabels();
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const filters = useMemo(() => ({ machine_id: machine?.id }), [machine]);
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      tenantMlService.observations(
        { page: q.page, page_size: q.page_size, filters: q.filters },
        signal,
      ),
    [],
  );
  const columns: DataColumn<TenantPredictionDto>[] = [
    {
      id: 'week',
      header: 'Week ending',
      render: (p) => formatInstantIn(p.week_ending, timeZone),
    },
    {
      id: 'machine',
      header: 'Machine',
      render: (p) => (
        <Link component={RouterLink} to={machineDetailPath(p.machine_id)}>
          {machineName(p.machine_id)}
        </Link>
      ),
    },
    {
      id: 'observations',
      header: 'What was unusual',
      render: (p) =>
        p.observations.length === 0 ? (
          'Unusual pattern compared with this machine’s history — needs review'
        ) : (
          <Box component="ul" className="m-0 pl-4">
            {p.observations.map((o) => (
              <li key={o}>
                <Typography variant="body2">{o}</Typography>
              </li>
            ))}
          </Box>
        ),
    },
    {
      id: 'case',
      header: 'Case',
      render: (p) =>
        p.case_id === null ? (
          '—'
        ) : (
          <Link component={RouterLink} to={caseDetailPath(p.case_id)}>
            Open case
          </Link>
        ),
    },
  ];
  return (
    <Box className="flex flex-col gap-3">
      <Alert severity="info">{OBSERVATIONS_NOTICE}</Alert>
      <ServerDataTable<TenantPredictionDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(p) => p.id}
        filters={filters}
        searchable={false}
        emptyTitle="No observations to review"
        emptyDescription="Observations appear here only when an approved, active model surfaces one for review."
        toolbar={
          <Box className="min-w-56">
            <MachinePicker value={machine} onChange={setMachine} />
          </Box>
        }
      />
    </Box>
  );
}
