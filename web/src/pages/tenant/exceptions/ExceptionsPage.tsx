import { Alert, Box, Chip, MenuItem, Stack, TextField } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';
import { jobService } from '../../../api/services/jobService';
import { meterService } from '../../../api/services/meterService';
import type { ExceptionDto, JobDto } from '../../../api/types';
import { AsyncAutocomplete } from '../../../components/data/AsyncAutocomplete';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import {
  EXCEPTION_TYPE_LABELS,
  explainException,
  NEUTRAL_REVIEW_NOTICE,
} from '../../../components/meter/exceptionText';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { useMachineLabels } from '../shared/useMachineLabels';
import {
  EXCEPTION_STATUS_LABELS,
  EXCEPTION_STATUS_OPTIONS,
  EXCEPTION_STATUS_TONES,
  EXCEPTION_TYPE_OPTIONS,
} from './exceptionDisplay';
import { ExceptionDetailDialog } from './ExceptionDetailDialog';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';

/** Meter/GPS exceptions awaiting or after human review; filtered by status, type and job. */
export function ExceptionsPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const machineName = useMachineLabels();
  const [params, setParams] = useSearchParams();
  const jobId = params.get('job_id') ?? '';
  const [status, setStatus] = useState('OPEN');
  const [type, setType] = useState('');
  const [job, setJob] = useState<JobDto | null>(null);
  const [selected, setSelected] = useState<ExceptionDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const liveReload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  useLiveRefresh([ENTITY.meterException, ENTITY.meterCapture], liveReload);
  const filters = useMemo(
    () => ({
      status: status || undefined,
      exception_type: type || undefined,
      job_id: jobId || undefined,
    }),
    [status, type, jobId],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      meterService.listExceptions(
        { page: q.page, page_size: q.page_size, filters: q.filters },
        signal,
      ),
    [],
  );
  const fetchJobs = useCallback(
    async (q: string, signal: AbortSignal) =>
      (await jobService.list({ page: 1, page_size: 20, q }, signal)).items,
    [],
  );
  // A job_id deep link (e.g. "Review exceptions" on a job) is shown by its job number, not its id.
  const loadUrlJob = useCallback(
    async (signal: AbortSignal) => (await jobService.summary(jobId, signal)).job,
    [jobId],
  );
  const urlJob = useAsyncResource(loadUrlJob, [], jobId !== '' && job === null);
  const shownJob = job ?? (urlJob.data?.id === jobId ? urlJob.data : null);
  const setJobFilter = (j: JobDto | null) => {
    setJob(j);
    setParams(j === null ? {} : { job_id: j.id }, { replace: true });
  };
  const columns: DataColumn<ExceptionDto>[] = [
    { id: 'created', header: 'Recorded', render: (e) => formatInstantIn(e.created_at, timeZone) },
    { id: 'type', header: 'Type', render: (e) => EXCEPTION_TYPE_LABELS[e.exception_type] },
    {
      id: 'status',
      header: 'Status',
      render: (e) => (
        <StatusChip
          status={e.status}
          tones={EXCEPTION_STATUS_TONES}
          label={EXCEPTION_STATUS_LABELS[e.status]}
        />
      ),
    },
    { id: 'machine', header: 'Machine', render: (e) => machineName(e.machine_id) },
    {
      id: 'explanation',
      header: 'What was recorded',
      render: (e) => explainException(e.exception_type, e.evidence),
    },
    {
      id: 'blocking',
      header: 'Billing',
      render: (e) =>
        e.blocking ? <Chip size="small" variant="outlined" label="Blocks billing" /> : '—',
    },
  ];
  return (
    <>
      <PageHeader
        title="Exceptions"
        subtitle="Meter and GPS evidence that requires review before billing"
      />
      <Stack spacing={2}>
        <Alert severity="info">{NEUTRAL_REVIEW_NOTICE}</Alert>
        <ServerDataTable<ExceptionDto>
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(e) => e.id}
          filters={filters}
          searchable={false}
          emptyTitle="No exceptions match these filters"
          reloadKey={reloadKey}
          onRowClick={setSelected}
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
                sx={{ minWidth: 220 }}
              >
                <MenuItem value="">All statuses</MenuItem>
                {EXCEPTION_STATUS_OPTIONS.map((o) => (
                  <MenuItem key={o.value} value={o.value}>
                    {o.label}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                size="small"
                label="Type"
                value={type}
                onChange={(e) => {
                  setType(e.target.value);
                }}
                sx={{ minWidth: 240 }}
              >
                <MenuItem value="">All types</MenuItem>
                {EXCEPTION_TYPE_OPTIONS.map((o) => (
                  <MenuItem key={o.value} value={o.value}>
                    {o.label}
                  </MenuItem>
                ))}
              </TextField>
              <Box className="min-w-64">
                <AsyncAutocomplete<JobDto>
                  label="Job"
                  value={shownJob}
                  onChange={setJobFilter}
                  fetchOptions={fetchJobs}
                  getOptionLabel={(j) => j.job_number}
                  isOptionEqualToValue={(a, b) => a.id === b.id}
                />
              </Box>
              {jobId !== '' && shownJob === null && urlJob.error !== null && (
                <Chip
                  label="Filtered by one job"
                  onDelete={() => {
                    setJobFilter(null);
                  }}
                />
              )}
            </>
          }
        />
      </Stack>
      {selected !== null && (
        <ExceptionDetailDialog
          exception={selected}
          machineName={machineName(selected.machine_id)}
          timeZone={timeZone}
          onClose={() => {
            setSelected(null);
          }}
          onReviewed={() => {
            notify.success('Review recorded.');
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
