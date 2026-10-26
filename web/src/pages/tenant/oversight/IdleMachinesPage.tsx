import { Box, Link } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router';
import type { IdleMachineDto } from '../../../api/oversightTypes';
import { oversightService } from '../../../api/services/oversightService';
import type { CategoryDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { jobDetailPath, machineDetailPath } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import { CategoryFilter } from '../shared/lookupPickers';
import { machineText, nameOr } from '../shared/names';

const stop = (e: { stopPropagation: () => void }) => {
  e.stopPropagation();
};

function JobLink({ id, number }: { id: string | null; number: string | null | undefined }) {
  if (id === null) return <span>—</span>;
  return (
    <Link component={RouterLink} to={jobDetailPath(id)} onClick={stop}>
      {nameOr(number, id)}
    </Link>
  );
}

/**
 * Idle machines (DEC-031 M2): active machines with no running job and no engine hours for the
 * company's days, longest idle first; an approved job not started yet is shown as planned.
 */
export function IdleMachinesPage() {
  const timeZone = useDisplayTimeZone();
  const navigate = useNavigate();
  const [category, setCategory] = useState<CategoryDto | null>(null);
  const fetchPage = useCallback<FetchPage<IdleMachineDto>>(
    (query, signal) => oversightService.listIdleMachines(query, signal),
    [],
  );
  const when = (v: string | null) => (v === null ? '—' : formatInstantIn(v, timeZone));
  const columns: DataColumn<IdleMachineDto>[] = [
    {
      id: 'machine',
      header: 'Machine',
      render: (m) => (
        <Link component={RouterLink} to={machineDetailPath(m.machine_id)} onClick={stop}>
          {machineText(m.machine_code, m.machine_name, m.machine_id)}
        </Link>
      ),
    },
    { id: 'days', header: 'Idle days', align: 'right', render: (m) => m.idle_days },
    { id: 'since', header: 'Idle since', render: (m) => formatInstantIn(m.idle_since, timeZone) },
    {
      id: 'last_job',
      header: 'Last job',
      render: (m) => <JobLink id={m.last_job_id} number={m.last_job_number} />,
    },
    { id: 'last_completed', header: 'Completed', render: (m) => when(m.last_job_completed_at) },
    {
      id: 'engine',
      header: 'Last engine activity',
      render: (m) => when(m.last_engine_activity_at),
    },
    {
      id: 'planned',
      header: 'Planned job',
      render: (m) => <JobLink id={m.planned_job_id} number={m.planned_job_number} />,
    },
  ];
  return (
    <>
      <PageHeader
        title="Idle machines"
        subtitle="Active machines with no running job and no engine hours for the company's set days"
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(m) => m.machine_id}
        searchPlaceholder="Search asset code or name"
        filters={{ category_id: category?.id }}
        emptyTitle="No idle machines"
        emptyDescription="Machines appear here once they pass the company's idle days without work."
        onRowClick={(m) => {
          void navigate(machineDetailPath(m.machine_id));
        }}
        toolbar={
          <Box sx={{ minWidth: 240 }}>
            <CategoryFilter label="Category" value={category} onChange={setCategory} />
          </Box>
        }
      />
    </>
  );
}
