import { Typography } from '@mui/material';
import { useCallback } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { machineService } from '../../../api/services/machineService';
import type { TrackerAssignmentDto, TrackerDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { DetailSection } from '../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { machineDetailPath } from '../../../navigation/routes';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { machineLabel } from '../shared/display';

interface Props {
  tracker: TrackerDto;
  timeZone: string;
}

/** Current machine assignment with this tracker's effective-dated history on that machine. */
export function TrackerAssignmentSection({ tracker, timeZone }: Props) {
  const { hasPermission } = useSession();
  const canMachines = hasPermission(PERMISSIONS.tenantMachineRead);
  const current = tracker.current_assignment ?? null;
  const machineId = current?.machine_id ?? null;
  const load = useCallback(
    async (signal: AbortSignal) => {
      if (machineId === null) return null;
      const [machine, history] = await Promise.all([
        machineService.get(machineId, signal),
        machineService.listTrackerAssignments(machineId, signal),
      ]);
      return { machine, history: history.filter((a) => a.tracker_id === tracker.id) };
    },
    [machineId, tracker.id],
  );
  const resource = useAsyncResource(load, [], canMachines && machineId !== null);

  if (current === null) {
    return (
      <DetailSection title="Assignment">
        <Typography variant="body2" color="text.secondary">
          Not assigned to a machine. Past assignments are listed on each machine&apos;s Tracker
          history tab.
        </Typography>
      </DetailSection>
    );
  }
  const name = resource.data?.machine !== undefined ? machineLabel(resource.data.machine) : null;
  const columns: DataColumn<TrackerAssignmentDto>[] = [
    {
      id: 'role',
      header: 'Role',
      render: (a) => (a.is_primary ? 'Primary' : 'Additional'),
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
    <DetailSection title="Assignment">
      <KeyValueGrid
        columns={4}
        items={[
          {
            label: 'Machine',
            value: (
              <RouterLink to={machineDetailPath(current.machine_id)}>
                {name ?? `${current.machine_id.slice(0, 8)}…`}
              </RouterLink>
            ),
          },
          { label: 'Primary', value: current.is_primary ? 'Yes' : 'No' },
          { label: 'Since', value: formatInstantIn(current.effective_from, timeZone) },
          { label: 'Reason', value: current.reason ?? '—' },
        ]}
      />
      {canMachines && (
        <>
          <Typography variant="subtitle2" component="h3" className="mt-4 mb-1">
            History on this machine
          </Typography>
          <AsyncContent
            resource={resource}
            errorTitle="Could not load assignment history"
            isEmpty={(d) => d === null || d.history.length === 0}
            emptyTitle="No earlier assignments on this machine"
          >
            {(d) => (
              <StaticTable
                ariaLabel="Assignment history"
                columns={columns}
                rows={d?.history ?? []}
                getRowId={(a) => a.id}
              />
            )}
          </AsyncContent>
        </>
      )}
    </DetailSection>
  );
}
