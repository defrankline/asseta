import Add from '@mui/icons-material/Add';
import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { machineService } from '../../../api/services/machineService';
import { staffService } from '../../../api/services/staffService';
import type { AssignmentDto, StaffDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNotify } from '../../../notifications/useNotify';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import { AssignStaffDialog } from './AssignStaffDialog';
import { EndAssignmentDialog } from './EndAssignmentDialog';

interface StaffAssignmentsTabProps {
  machineId: string;
  timeZone: string;
}

interface Loaded {
  assignments: AssignmentDto[];
  staff: ReadonlyMap<string, StaffDto>;
}

/** Effective-dated supervisor/operator assignments for one machine. */
export function StaffAssignmentsTab({ machineId, timeZone }: StaffAssignmentsTabProps) {
  const notify = useNotify();
  const [assigning, setAssigning] = useState(false);
  const [ending, setEnding] = useState<AssignmentDto | null>(null);
  const load = useCallback(
    async (signal: AbortSignal): Promise<Loaded> => {
      const [assignments, staff] = await Promise.all([
        machineService.listAssignments(machineId, signal),
        staffService.list({ page: 1, page_size: 200 }, signal),
      ]);
      return { assignments, staff: new Map(staff.items.map((s) => [s.id, s])) };
    },
    [machineId],
  );
  const resource = useAsyncResource(load);
  const nameOf = (id: string) => resource.data?.staff.get(id)?.full_name ?? id;

  const columns: DataColumn<AssignmentDto>[] = [
    { id: 'staff', header: 'Staff member', render: (a) => nameOf(a.staff_member_id) },
    { id: 'role', header: 'Role', render: (a) => humanize(a.role) },
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
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (a) =>
        a.effective_to === null ? (
          <CanMutate permission={PERMISSIONS.tenantStaffWrite}>
            <Button
              size="small"
              onClick={() => {
                setEnding(a);
              }}
            >
              End
            </Button>
          </CanMutate>
        ) : null,
    },
  ];

  return (
    <Box>
      <CanMutate permission={PERMISSIONS.tenantStaffWrite}>
        <Box className="mb-2 flex justify-end">
          <Button
            startIcon={<Add />}
            variant="outlined"
            onClick={() => {
              setAssigning(true);
            }}
          >
            Assign staff
          </Button>
        </Box>
      </CanMutate>
      <AsyncContent
        resource={resource}
        isEmpty={(d) => d.assignments.length === 0}
        emptyTitle="No staff assigned"
        emptyDescription="Assign a supervisor or operator with an effective start time."
        errorTitle="Could not load assignments"
      >
        {(d) => (
          <StaticTable
            ariaLabel="Staff assignments"
            columns={columns}
            rows={d.assignments}
            getRowId={(a) => a.id}
          />
        )}
      </AsyncContent>
      {assigning && (
        <AssignStaffDialog
          machineId={machineId}
          timeZone={timeZone}
          onClose={() => {
            setAssigning(false);
          }}
          onAssigned={() => {
            notify.success('Staff assigned.');
            resource.reload();
          }}
        />
      )}
      {ending !== null && (
        <EndAssignmentDialog
          assignment={ending}
          staffName={nameOf(ending.staff_member_id)}
          timeZone={timeZone}
          onClose={() => {
            setEnding(null);
          }}
          onEnded={() => {
            notify.success('Assignment ended.');
            resource.reload();
          }}
        />
      )}
    </Box>
  );
}
