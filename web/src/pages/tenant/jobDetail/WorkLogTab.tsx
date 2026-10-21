import Add from '@mui/icons-material/Add';
import { Box, Button, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { jobService } from '../../../api/services/jobService';
import type { ActivityDto, JobDto, JobStatus } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNotify } from '../../../notifications/useNotify';
import { formatDuration, formatInstantIn } from '../../../utils/time';
import { labelOf } from '../shared/display';
import { ACTIVITY_TYPE_OPTIONS } from '../shared/jobDisplay';
import { ActivityDialog } from './ActivityDialog';

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
            onChanged();
          }}
        />
      )}
    </Stack>
  );
}
