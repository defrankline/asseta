import { useCallback } from 'react';
import { machineService } from '../../../api/services/machineService';
import type { TrackerAssignmentDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { formatInstantIn } from '../../../utils/time';

interface TrackerHistoryTabProps {
  machineId: string;
  timeZone: string;
}

/** Effective-dated tracker assignment history (one active primary per machine). */
export function TrackerHistoryTab({ machineId, timeZone }: TrackerHistoryTabProps) {
  const load = useCallback(
    (signal: AbortSignal) => machineService.listTrackerAssignments(machineId, signal),
    [machineId],
  );
  const resource = useAsyncResource(load);
  const columns: DataColumn<TrackerAssignmentDto>[] = [
    {
      id: 'tracker',
      header: 'Tracker',
      render: (a) => <span className="font-mono text-xs">{a.tracker_id}</span>,
    },
    {
      id: 'primary',
      header: 'Role',
      render: (a) =>
        a.is_primary ? (
          <StatusChip status="PRIMARY" tones={{ PRIMARY: 'info' }} label="Primary" />
        ) : (
          <StatusChip status="SECONDARY" label="Additional" />
        ),
    },
    { id: 'from', header: 'From', render: (a) => formatInstantIn(a.effective_from, timeZone) },
    {
      id: 'to',
      header: 'To',
      render: (a) =>
        a.effective_to === null ? (
          <StatusChip status="CURRENT" tones={{ CURRENT: 'success' }} label="Current" />
        ) : (
          formatInstantIn(a.effective_to, timeZone)
        ),
    },
    { id: 'reason', header: 'Reason', render: (a) => a.reason ?? '—' },
  ];
  return (
    <AsyncContent
      resource={resource}
      isEmpty={(rows) => rows.length === 0}
      emptyTitle="No tracker has been assigned"
      errorTitle="Could not load tracker assignments"
    >
      {(rows) => (
        <StaticTable
          ariaLabel="Tracker assignments"
          columns={columns}
          rows={rows}
          getRowId={(a) => a.id}
        />
      )}
    </AsyncContent>
  );
}
