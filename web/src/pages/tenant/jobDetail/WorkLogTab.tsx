import Add from '@mui/icons-material/Add';
import { Box, Button, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { CAPABILITY, useCapabilityEnabled } from '../../../access/capabilities';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { jobService } from '../../../api/services/jobService';
import { revenueService } from '../../../api/services/revenueService';
import type { ActivityDto, JobDto, JobStatus, NonRevenueActivityDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { recordPath } from '../../../navigation/recordRoutes';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatDuration, formatInstantIn } from '../../../utils/time';
import { labelOf } from '../shared/display';
import { ACTIVITY_TYPE_OPTIONS } from '../shared/jobDisplay';
import { ACTIVITY_STATUS_LABELS, ACTIVITY_STATUS_TONES } from '../revenue/revenueDisplay';
import { useExplainActivity } from '../revenue/revenueKits';
import { ActivityDialog } from './ActivityDialog';

/** Enough for one job's work log; the server returns its non-revenue entries newest first. */
const NON_REVENUE_PAGE = 200;

/**
 * Non-revenue status of the job's work-log entries (revenue checks on and readable), keyed by
 * entry id: until approved by a second person the time counts as revenue.
 */
function useNonRevenueStatus(jobId: string) {
  const { hasPermission } = useSession();
  const enabled =
    useCapabilityEnabled(CAPABILITY.revenue) && hasPermission(PERMISSIONS.tenantRevenueRead);
  const load = useCallback(
    async (signal: AbortSignal): Promise<ReadonlyMap<string, NonRevenueActivityDto>> => {
      if (!enabled) return new Map();
      const page = await revenueService.listActivities(
        { page: 1, page_size: NON_REVENUE_PAGE, filters: { job_id: jobId } },
        signal,
      );
      return new Map(page.items.map((a) => [a.activity_id, a]));
    },
    [enabled, jobId],
  );
  return { enabled, resource: useAsyncResource(load) };
}

const LOGGABLE: readonly JobStatus[] = ['APPROVED', 'IN_PROGRESS', 'COMPLETED'];

function duration(a: ActivityDto): string {
  if (a.ended_at === null) return 'Open';
  return formatDuration((Date.parse(a.ended_at) - Date.parse(a.started_at)) / 1000);
}

interface WorkLogTabProps {
  job: JobDto;
  timeZone: string;
  onChanged: () => void;
}

/** Supervisor work log: work, standby, downtime and notes for the job. */
export function WorkLogTab({ job, timeZone, onChanged }: WorkLogTabProps) {
  const notify = useNotify();
  const canLog = useCanMutate(PERMISSIONS.tenantJobLog) && LOGGABLE.includes(job.status);
  const [adding, setAdding] = useState(false);
  const load = useCallback(
    (signal: AbortSignal) => jobService.listActivities(job.id, signal),
    [job.id],
  );
  const resource = useAsyncResource(load);
  const nonRevenue = useNonRevenueStatus(job.id);
  const reloadNonRevenue = nonRevenue.resource.reload;
  const explain = useExplainActivity(() => {
    reloadNonRevenue();
    onChanged();
  });
  const revenueCell = (a: ActivityDto) => {
    const entry = nonRevenue.resource.data?.get(a.id);
    if (entry === undefined) return '—';
    return (
      <Box className="flex flex-wrap items-center gap-1">
        {entry.approval_id === null ? (
          <StatusChip
            status={entry.approval_status}
            tones={ACTIVITY_STATUS_TONES}
            label={ACTIVITY_STATUS_LABELS[entry.approval_status]}
          />
        ) : (
          <Button
            size="small"
            component={RouterLink}
            to={recordPath('NON_REVENUE_APPROVAL', entry.approval_id)}
          >
            {ACTIVITY_STATUS_LABELS[entry.approval_status]}
          </Button>
        )}
        {explain.canExplain(entry) && (
          <Button
            size="small"
            onClick={() => {
              explain.open(entry);
            }}
          >
            Explain
          </Button>
        )}
      </Box>
    );
  };
  const columns: DataColumn<ActivityDto>[] = [
    { id: 'type', header: 'Type', render: (a) => labelOf(ACTIVITY_TYPE_OPTIONS, a.activity_type) },
    { id: 'start', header: 'Start', render: (a) => formatInstantIn(a.started_at, timeZone) },
    { id: 'end', header: 'End', render: (a) => formatInstantIn(a.ended_at, timeZone) },
    { id: 'duration', header: 'Duration', render: duration },
    {
      id: 'billable',
      header: 'Billable',
      render: (a) =>
        a.billable ? (
          <StatusChip status="BILLABLE" tones={{ BILLABLE: 'success' }} label="Billable" />
        ) : (
          <StatusChip status="NON_BILLABLE" label="Non-billable" />
        ),
    },
    { id: 'note', header: 'Note', render: (a) => a.note ?? '—' },
    ...(nonRevenue.enabled
      ? [{ id: 'revenue', header: 'Non-revenue approval', render: revenueCell }]
      : []),
  ];
  return (
    <Stack spacing={2}>
      {canLog && (
        <Box className="flex justify-end">
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => {
              setAdding(true);
            }}
          >
            Log activity
          </Button>
        </Box>
      )}
      <AsyncContent
        resource={resource}
        isEmpty={(d) => d.length === 0}
        emptyTitle="No work log entries"
        errorTitle="Could not load the work log"
      >
        {(d) => (
          <StaticTable ariaLabel="Work log" columns={columns} rows={d} getRowId={(a) => a.id} />
        )}
      </AsyncContent>
      {explain.dialog}
      {adding && (
        <ActivityDialog
          job={job}
          timeZone={timeZone}
          onClose={() => {
            setAdding(false);
          }}
          onLogged={() => {
            notify.success('Activity logged.');
            resource.reload();
            reloadNonRevenue();
            onChanged();
          }}
        />
      )}
    </Stack>
  );
}
