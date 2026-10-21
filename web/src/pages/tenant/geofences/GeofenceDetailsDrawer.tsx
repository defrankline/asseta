import { Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { GeofenceDto, JobSiteDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import { DetailsDrawer } from '../../../components/lifecycle/DetailsDrawer';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { machineDetailPath } from '../../../navigation/routes';
import { GEOFENCE_KIND_OPTIONS, labelOf } from '../shared/display';
import { jobSiteLabel } from '../shared/lookups';
import { formatArea } from './geofenceForm';

interface GeofenceDetailsDrawerProps {
  geofence: GeofenceDto;
  site: JobSiteDto | null;
  machineLabels: ReadonlyMap<string, string>;
  actions: readonly RowAction[];
  onClose: () => void;
}

/** Every field of a geofence with its job site and the machines it applies to. */
export function GeofenceDetailsDrawer({
  geofence: g,
  site,
  machineLabels,
  actions,
  onClose,
}: GeofenceDetailsDrawerProps) {
  return (
    <DetailsDrawer
      title={`Geofence ${g.name}`}
      status={<ActiveChip active={g.is_active} />}
      actions={<ActionButtons actions={actions} />}
      onClose={onClose}
    >
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Name', value: g.name },
          { label: 'Kind', value: labelOf(GEOFENCE_KIND_OPTIONS, g.kind) },
          { label: 'Shape', value: g.shape === 'CORRIDOR' ? 'Corridor' : 'Polygon' },
          {
            label: 'Corridor width',
            value: g.corridor_width_m === null ? '—' : `${String(g.corridor_width_m)} m`,
          },
          {
            label: 'Computed area',
            value: `${formatArea(g.area_m2)} (${g.area_m2.toFixed(0)} m²)`,
          },
          { label: 'Job site', value: site === null ? '—' : jobSiteLabel(site) },
          { label: 'Deactivated', value: g.deactivated_at ?? '—' },
          { label: 'Deactivation reason', value: g.deactivation_reason ?? '—' },
          { label: 'Version', value: String(g.version) },
        ]}
      />
      <Typography variant="subtitle2" component="h3">
        Applies to
      </Typography>
      {g.machine_ids.length === 0 ? (
        <Typography variant="body2">All machines</Typography>
      ) : (
        <ul className="m-0 pl-5">
          {g.machine_ids.map((id) => (
            <li key={id}>
              <RouterLink to={machineDetailPath(id)}>
                {machineLabels.get(id) ?? `${id.slice(0, 8)}…`}
              </RouterLink>
            </li>
          ))}
        </ul>
      )}
    </DetailsDrawer>
  );
}
