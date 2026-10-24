import ChevronRight from '@mui/icons-material/ChevronRight';
import {
  Button,
  Chip,
  Paper,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router';
import { jobService } from '../../../api/services/jobService';
import type { JobDto, Page } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { fieldJobPath } from '../../../navigation/routes';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { formatInstantIn } from '../../../utils/time';
import { labelOf } from '../shared/display';
import { JOB_STATUS_OPTIONS, JOB_STATUS_TONES } from '../shared/jobDisplay';
import { useFieldMachineLabels, useSeesAllJobs } from './fieldLookups';
import { FIELD_JOB_SECTIONS } from './fieldWork';

type Scope = 'mine' | 'all';

/** Supervisor job list (Field work): in progress, ready to start and recently closed. */
export function MyJobsPage() {
  const timeZone = useDisplayTimeZone();
  const navigate = useNavigate();
  const seesAll = useSeesAllJobs();
  // Job managers are often not linked to a staff record, so they start on every job.
  const [scope, setScope] = useState<Scope>(seesAll ? 'all' : 'mine');
  const machineLabel = useFieldMachineLabels();
  const load = useCallback(
    (signal: AbortSignal): Promise<Page<JobDto>[]> =>
      Promise.all(
        FIELD_JOB_SECTIONS.map((s) =>
          jobService.list(
            {
              page: 1,
              page_size: s.pageSize,
              filters: { status: s.status, mine: scope === 'mine' ? 'true' : undefined },
            },
            signal,
          ),
        ),
      ),
    [scope],
  );
  const resource = useAsyncResource(load);
  useLiveRefresh([ENTITY.job], resource.reload);
  const columns: DataColumn<JobDto>[] = [
    {
      id: 'job',
      header: 'Job',
      render: (j) => (
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {j.job_number}
        </Typography>
      ),
    },
    { id: 'machine', header: 'Machine', render: (j) => machineLabel(j.machine_id) },
    {
      id: 'planned',
      header: 'Planned start',
      render: (j) => formatInstantIn(j.planned_start, timeZone),
    },
    {
      id: 'when',
      header: 'Started / completed',
      render: (j) => formatInstantIn(j.completed_at ?? j.started_at, timeZone),
    },
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
    {
      id: 'open',
      header: '',
      align: 'right',
      render: (j) => (
        <Button
          size="small"
          component={RouterLink}
          to={fieldJobPath(j.id)}
          endIcon={<ChevronRight />}
          aria-label={`Open job ${j.job_number}`}
        >
          Open
        </Button>
      ),
    },
  ];
  return (
    <>
      <PageHeader
        title="My jobs"
        subtitle="Record opening and closing readings, start and complete jobs, log the work and the customer acknowledgement"
        actions={
          seesAll ? (
            <ToggleButtonGroup
              size="small"
              exclusive
              value={scope}
              aria-label="Jobs shown"
              onChange={(_e, v: Scope | null) => {
                if (v !== null) setScope(v);
              }}
            >
              <ToggleButton value="mine">Assigned to me</ToggleButton>
              <ToggleButton value="all">All jobs</ToggleButton>
            </ToggleButtonGroup>
          ) : undefined
        }
      />
      <AsyncContent
        resource={resource}
        errorTitle="Could not load jobs"
        loadingLabel="Loading jobs"
      >
        {(pages) =>
          pages.every((p) => p.total === 0) ? (
            <EmptyState
              title="No jobs to work on"
              description={
                scope === 'mine'
                  ? 'Jobs appear here once they are approved and you are their supervisor or assigned to their machine.'
                  : 'Jobs appear here once they are approved.'
              }
            />
          ) : (
            <Stack spacing={3}>
              {FIELD_JOB_SECTIONS.map((section, i) => {
                const page = pages[i];
                const rows = page?.items ?? [];
                return (
                  <Paper
                    key={section.key}
                    variant="outlined"
                    className="p-3"
                    component="section"
                    aria-label={section.title}
                  >
                    <Stack direction="row" spacing={1} className="mb-2 items-center">
                      <Typography variant="h6" component="h2">
                        {section.title}
                      </Typography>
                      <Chip size="small" label={String(page?.total ?? 0)} />
                    </Stack>
                    {rows.length === 0 ? (
                      <Typography variant="body2" color="text.secondary">
                        {section.empty}
                      </Typography>
                    ) : (
                      <StaticTable
                        ariaLabel={section.title}
                        columns={columns}
                        rows={rows}
                        getRowId={(j) => j.id}
                        onRowClick={(j) => {
                          void navigate(fieldJobPath(j.id));
                        }}
                      />
                    )}
                  </Paper>
                );
              })}
            </Stack>
          )
        }
      </AsyncContent>
    </>
  );
}
