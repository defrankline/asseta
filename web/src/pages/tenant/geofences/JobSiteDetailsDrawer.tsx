import { Typography } from '@mui/material';
import type { GeofenceDto, JobSiteDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import { DetailsDrawer } from '../../../components/lifecycle/DetailsDrawer';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { GEOFENCE_KIND_OPTIONS, labelOf } from '../shared/display';
import { jobSiteLabel } from '../shared/lookups';
import { formatArea } from './geofenceForm';

interface JobSiteDetailsDrawerProps {
  site: JobSiteDto;
  /** All loaded geofences; the ones on this site are listed as related records. */
  geofences: readonly GeofenceDto[];
  onOpenGeofence: (geofence: GeofenceDto) => void;
  /** Record commands (edit, deactivate / reactivate). */
  actions: readonly RowAction[];
  onClose: () => void;
}

/** Job site record with its geofences. */
export function JobSiteDetailsDrawer({
  site,
  geofences,
  onOpenGeofence,
  actions,
  onClose,
}: JobSiteDetailsDrawerProps) {
  const related = geofences.filter((g) => g.job_site_id === site.id);
  const columns: DataColumn<GeofenceDto>[] = [
    { id: 'name', header: 'Name', render: (g) => g.name },
    { id: 'kind', header: 'Kind', render: (g) => labelOf(GEOFENCE_KIND_OPTIONS, g.kind) },
    { id: 'area', header: 'Area', align: 'right', render: (g) => formatArea(g.area_m2) },
    { id: 'active', header: 'State', render: (g) => <ActiveChip active={g.is_active} /> },
  ];
  const [lon, lat] = site.center.coordinates;
  return (
    <DetailsDrawer
      title={`Job site ${jobSiteLabel(site)}`}
      status={<ActiveChip active={site.is_active} />}
      actions={<ActionButtons actions={actions} />}
      onClose={onClose}
    >
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Code', value: site.code },
          { label: 'Name', value: site.name },
          { label: 'Address', value: site.address ?? '—' },
          { label: 'Center (lat, lon)', value: `${lat.toFixed(5)}, ${lon.toFixed(5)}` },
          { label: 'Deactivated', value: site.deactivated_at ?? '—' },
          { label: 'Deactivation reason', value: site.deactivation_reason ?? '—' },
          { label: 'Version', value: String(site.version) },
        ]}
      />
      <Typography variant="subtitle2" component="h3">
        Geofences on this site
      </Typography>
      {related.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No geofences are linked to this site.
        </Typography>
      ) : (
        <StaticTable
          ariaLabel="Geofences on this site"
          columns={columns}
          rows={related}
          getRowId={(g) => g.id}
          isRowMuted={(g) => !g.is_active}
          onRowClick={onOpenGeofence}
        />
      )}
    </DetailsDrawer>
  );
}
