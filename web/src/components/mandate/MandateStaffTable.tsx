import type { ReactNode } from 'react';
import type { MandateAssignmentDto } from '../../api/types';
import { formatInstant } from '../../utils/dates';
import { StaticTable } from '../data/StaticTable';
import type { DataColumn } from '../data/ServerDataTable';
import { StatusChip } from '../display/StatusChip';
import { EmptyState } from '../feedback/EmptyState';

interface MandateStaffTableProps {
  assignments: readonly MandateAssignmentDto[];
  /** Optional per-row action (e.g. "Remove" for active assignments). */
  renderAction?: (a: MandateAssignmentDto) => ReactNode;
}

/** Staff assigned under a mandate, with the client role each holds and when access ended. */
export function MandateStaffTable({ assignments, renderAction }: MandateStaffTableProps) {
  if (assignments.length === 0) {
    return <EmptyState title="No staff assigned" description="Nobody has access under it yet." />;
  }
  const columns: DataColumn<MandateAssignmentDto>[] = [
    {
      id: 'staff',
      header: 'Staff',
      render: (a) => (
        <>
          <strong>{a.display_name}</strong>
          <br />
          {a.email}
        </>
      ),
    },
    { id: 'role', header: 'Client role', render: (a) => a.role_key },
    { id: 'assigned', header: 'Assigned', render: (a) => formatInstant(a.assigned_at) },
    {
      id: 'removed',
      header: 'Removed',
      render: (a) =>
        a.is_active ? (
          <StatusChip status="ACTIVE" tones={{ ACTIVE: 'success' }} label="Active" />
        ) : (
          formatInstant(a.removed_at)
        ),
    },
  ];
  if (renderAction !== undefined) {
    columns.push({ id: 'actions', header: 'Actions', align: 'right', render: renderAction });
  }
  return (
    <StaticTable
      columns={columns}
      rows={assignments}
      getRowId={(a) => a.id}
      ariaLabel="Staff with access"
    />
  );
}
