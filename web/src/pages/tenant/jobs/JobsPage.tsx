import Add from '@mui/icons-material/Add';
import { Box, Button, MenuItem, TextField } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { jobService } from '../../../api/services/jobService';
import type { JobDto, MachineDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { jobDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { labelOf } from '../shared/display';
import { JOB_STATUS_OPTIONS, JOB_STATUS_TONES, rateSourceLabel } from '../shared/jobDisplay';
import { MachinePicker } from '../shared/MachinePicker';
import { useMachineLabels } from '../shared/useMachineLabels';
import { CreateJobDialog } from './CreateJobDialog';

/** Rental jobs: server table with status / machine filters and job-number search. */
export function JobsPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const { hasPermission } = useSession();
  const machineName = useMachineLabels();
  const [creating, setCreating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [status, setStatus] = useState('');
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const filters = useMemo(
    () => ({ status: status || undefined, machine_id: machine?.id }),
    [status, machine],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      jobService.list({ page: q.page, page_size: q.page_size, q: q.q, filters: q.filters }, signal),
    [],
  );
  const columns: DataColumn<JobDto>[] = [
    { id: 'number', header: 'Job', render: (j) => <strong>{j.job_number}</strong> },
    {
      id: 'status',
      header: 'Status',
      render: (j) => (
        <StatusChip
          status={j.status}
          tones={JOB_STATUS_TONES}
          label={labelOf(JOB_STATUS_OPTIONS, j.status)}
        />
      ),
    },
    { id: 'machine', header: 'Machine', render: (j) => machineName(j.machine_id) },
    {
      id: 'start',
      header: 'Planned start',
      render: (j) => formatInstantIn(j.planned_start, timeZone),
    },
    {
      id: 'rate',
      header: 'Hourly rate',
      align: 'right',
      render: (j) => <MoneyText amount={j.hourly_rate} currency={j.currency} />,
    },
    { id: 'source', header: 'Rate source', render: (j) => rateSourceLabel(j.rate_source) },
  ];
  return (
    <>
      <PageHeader
        title="Jobs"
        subtitle="Contracted rental jobs: approval, meter readings, work logs and acknowledgements"
        actions={
          <CanMutate permission={PERMISSIONS.tenantJobWrite}>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setCreating(true);
              }}
            >
              New job
            </Button>
          </CanMutate>
        }
      />
      <ServerDataTable<JobDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(j) => j.id}
        filters={filters}
        searchPlaceholder="Search job number"
        emptyTitle="No jobs found"
        emptyDescription="Create a job against an active contract."
        reloadKey={reloadKey}
        onRowClick={(j) => {
          void navigate(jobDetailPath(j.id));
        }}
        toolbar={
          <>
            <TextField
              select
              size="small"
              label="Status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
              }}
              sx={{ minWidth: 180 }}
            >
              <MenuItem value="">All statuses</MenuItem>
              {JOB_STATUS_OPTIONS.map((o) => (
                <MenuItem key={o.value} value={o.value}>
                  {o.label}
                </MenuItem>
              ))}
            </TextField>
            {hasPermission(PERMISSIONS.tenantMachineRead) && (
              <Box className="min-w-64">
                <MachinePicker label="Machine filter" value={machine} onChange={setMachine} />
              </Box>
            )}
          </>
        }
      />
      {creating && (
        <CreateJobDialog
          timeZone={timeZone}
          onClose={() => {
            setCreating(false);
          }}
          onCreated={(j) => {
            notify.success(`Job ${j.job_number} created as draft.`);
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
