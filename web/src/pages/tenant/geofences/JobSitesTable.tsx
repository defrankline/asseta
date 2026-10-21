import type { JobSiteDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import type { RowAction } from '../../../components/lifecycle/rowActions';

interface JobSitesTableProps {
  rows: readonly JobSiteDto[];
  actionsFor: (s: JobSiteDto) => RowAction[];
}

/** Job site list; inactive sites are muted. */
export function JobSitesTable({ rows, actionsFor }: JobSitesTableProps) {
  const columns: DataColumn<JobSiteDto>[] = [
    { id: 'code', header: 'Code', render: (s) => s.code },
    { id: 'name', header: 'Name', render: (s) => s.name },
    { id: 'address', header: 'Address', render: (s) => s.address ?? '—' },
    {
      id: 'center',
      header: 'Center (lat, lon)',
      render: (s) => `${s.center.coordinates[1].toFixed(5)}, ${s.center.coordinates[0].toFixed(5)}`,
    },
    { id: 'active', header: 'State', render: (s) => <ActiveChip active={s.is_active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (s) => <RowActionsMenu label={`job site ${s.code}`} actions={actionsFor(s)} />,
    },
  ];
  return (
    <StaticTable
      ariaLabel="Job sites"
      columns={columns}
      rows={rows}
      getRowId={(s) => s.id}
      isRowMuted={(s) => !s.is_active}
    />
  );
}
