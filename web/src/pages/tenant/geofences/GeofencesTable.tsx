import { Chip } from '@mui/material';
import type { GeofenceDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { GEOFENCE_KIND_COLORS, GEOFENCE_KIND_OPTIONS, labelOf } from '../shared/display';
import { formatArea } from './geofenceForm';

interface GeofencesTableProps {
  rows: readonly GeofenceDto[];
  siteName: (id: string | null) => string;
  machineLabels: ReadonlyMap<string, string>;
  actionsFor: (g: GeofenceDto) => RowAction[];
  onSelect: (id: string) => void;
}

/** Geofence list; inactive geofences are muted. Clicking a name highlights it on the map. */
export function GeofencesTable({
  rows,
  siteName,
  machineLabels,
  actionsFor,
  onSelect,
}: GeofencesTableProps) {
  const columns: DataColumn<GeofenceDto>[] = [
    {
      id: 'name',
      header: 'Name',
      render: (g) => (
        <button
          type="button"
          className="cursor-pointer border-0 bg-transparent p-0 text-left font-semibold text-inherit underline"
          onClick={() => {
            onSelect(g.id);
          }}
        >
          {g.name}
        </button>
      ),
    },
    {
      id: 'kind',
      header: 'Kind',
      render: (g) => (
        <Chip
          size="small"
          variant="outlined"
          label={labelOf(GEOFENCE_KIND_OPTIONS, g.kind)}
          sx={{ borderColor: GEOFENCE_KIND_COLORS[g.kind], color: GEOFENCE_KIND_COLORS[g.kind] }}
        />
      ),
    },
    {
      id: 'shape',
      header: 'Shape',
      render: (g) =>
        g.shape === 'CORRIDOR' ? `Corridor · ${String(g.corridor_width_m ?? '?')} m` : 'Polygon',
    },
    { id: 'area', header: 'Area', align: 'right', render: (g) => formatArea(g.area_m2) },
    { id: 'site', header: 'Job site', render: (g) => siteName(g.job_site_id) },
    {
      id: 'machines',
      header: 'Applies to',
      render: (g) =>
        g.machine_ids.length === 0
          ? 'All machines'
          : g.machine_ids.map((id) => machineLabels.get(id) ?? id.slice(0, 8)).join(', '),
    },
    { id: 'active', header: 'State', render: (g) => <ActiveChip active={g.is_active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (g) => <RowActionsMenu label={`geofence ${g.name}`} actions={actionsFor(g)} />,
    },
  ];
  return (
    <StaticTable
      ariaLabel="Geofences"
      columns={columns}
      rows={rows}
      getRowId={(g) => g.id}
      isRowMuted={(g) => !g.is_active}
    />
  );
}
