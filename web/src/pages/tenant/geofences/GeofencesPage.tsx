import Add from '@mui/icons-material/Add';
import { Box, Button, Chip, Paper, Stack, Typography } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { geofenceService } from '../../../api/services/geofenceService';
import { machineService } from '../../../api/services/machineService';
import type { GeofenceDto, JobSiteDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import {
  GEOFENCE_KIND_COLORS,
  GEOFENCE_KIND_OPTIONS,
  labelOf,
  machineLabel,
} from '../shared/display';
import { formatArea } from './geofenceForm';
import { GeofenceDialog } from './GeofenceDialog';
import { GeofencesMap } from './GeofencesMap';
import { JobSiteDialog } from './JobSiteDialog';

type Editing = { kind: 'new' } | { kind: 'edit'; geofence: GeofenceDto } | null;

const NO_SITES: readonly JobSiteDto[] = [];

/** Job sites and geofences with a map preview; draw / edit geofences. */
export function GeofencesPage() {
  const notify = useNotify();
  const { hasPermission } = useSession();
  const canWrite = useCanMutate(PERMISSIONS.tenantGeofenceWrite);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editing, setEditing] = useState<Editing>(null);
  const [creatingSite, setCreatingSite] = useState(false);
  const [lastSaved, setLastSaved] = useState<GeofenceDto | null>(null);

  const loadGeofences = useCallback((signal: AbortSignal) => geofenceService.list(signal), []);
  const geofences = useAsyncResource(loadGeofences);
  const loadSites = useCallback((signal: AbortSignal) => geofenceService.listJobSites(signal), []);
  const sites = useAsyncResource(loadSites);
  // Machine names for "applies to" (best effort; needs tenant.machine.read).
  const canMachines = hasPermission(PERMISSIONS.tenantMachineRead);
  const loadMachines = useCallback(
    (signal: AbortSignal) => machineService.list({ page: 1, page_size: 200 }, signal),
    [],
  );
  const machines = useAsyncResource(loadMachines, [], canMachines);
  const machineLabels = useMemo(
    () => new Map((machines.data?.items ?? []).map((m) => [m.id, machineLabel(m)])),
    [machines.data],
  );
  const siteList = sites.data ?? NO_SITES;
  const siteName = (id: string | null) => {
    const s = id === null ? undefined : siteList.find((x) => x.id === id);
    return s === undefined ? '—' : `${s.code} · ${s.name}`;
  };

  const geofenceColumns: DataColumn<GeofenceDto>[] = [
    {
      id: 'name',
      header: 'Name',
      render: (g) => (
        <button
          type="button"
          className="cursor-pointer border-0 bg-transparent p-0 text-left font-semibold text-inherit underline"
          onClick={() => {
            setSelectedId(g.id);
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
    { id: 'active', header: 'Active', render: (g) => (g.is_active ? 'Yes' : 'No') },
    ...(canWrite
      ? [
          {
            id: 'actions',
            header: '',
            align: 'right' as const,
            render: (g: GeofenceDto) => (
              <Button
                size="small"
                onClick={() => {
                  setEditing({ kind: 'edit', geofence: g });
                }}
              >
                Edit
              </Button>
            ),
          },
        ]
      : []),
  ];

  const siteColumns: DataColumn<JobSiteDto>[] = [
    { id: 'code', header: 'Code', render: (s) => s.code },
    { id: 'name', header: 'Name', render: (s) => s.name },
    { id: 'address', header: 'Address', render: (s) => s.address ?? '—' },
    {
      id: 'center',
      header: 'Center (lat, lon)',
      render: (s) => `${s.center.coordinates[1].toFixed(5)}, ${s.center.coordinates[0].toFixed(5)}`,
    },
    { id: 'active', header: 'Active', render: (s) => (s.is_active ? 'Yes' : 'No') },
  ];

  return (
    <>
      <PageHeader
        title="Sites & geofences"
        subtitle="Job sites, allowed / restricted areas and corridors"
        actions={
          <CanMutate permission={PERMISSIONS.tenantGeofenceWrite}>
            <Button
              onClick={() => {
                setCreatingSite(true);
              }}
            >
              New job site
            </Button>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setEditing({ kind: 'new' });
              }}
            >
              New geofence
            </Button>
          </CanMutate>
        }
      />
      <Stack spacing={3}>
        {lastSaved !== null && (
          <Paper variant="outlined" className="p-3" role="status">
            <Typography variant="body2">
              Saved <strong>{lastSaved.name}</strong> · computed area{' '}
              <strong>{formatArea(lastSaved.area_m2)}</strong> ({lastSaved.area_m2.toFixed(0)} m²)
            </Typography>
          </Paper>
        )}
        <Box className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Paper variant="outlined" className="p-2">
            {geofences.data !== null && (
              <GeofencesMap
                geofences={geofences.data}
                sites={siteList}
                selectedId={selectedId}
                onSelect={setSelectedId}
              />
            )}
          </Paper>
          <Paper variant="outlined" className="p-3">
            <Typography variant="subtitle1" component="h2" className="mb-2">
              Geofences
            </Typography>
            <AsyncContent
              resource={geofences}
              isEmpty={(g) => g.length === 0}
              emptyTitle="No geofences yet"
              emptyDescription="Draw allowed areas, restricted areas or corridors to get location alerts."
            >
              {(rows) => (
                <StaticTable
                  ariaLabel="Geofences"
                  columns={geofenceColumns}
                  rows={rows}
                  getRowId={(g) => g.id}
                />
              )}
            </AsyncContent>
          </Paper>
        </Box>
        <Paper variant="outlined" className="p-3">
          <Typography variant="subtitle1" component="h2" className="mb-2">
            Job sites
          </Typography>
          <AsyncContent
            resource={sites}
            isEmpty={(s) => s.length === 0}
            emptyTitle="No job sites yet"
          >
            {(rows) => (
              <StaticTable
                ariaLabel="Job sites"
                columns={siteColumns}
                rows={rows}
                getRowId={(s) => s.id}
              />
            )}
          </AsyncContent>
        </Paper>
      </Stack>
      {editing !== null && (
        <GeofenceDialog
          {...(editing.kind === 'edit' ? { geofence: editing.geofence } : {})}
          sites={siteList}
          machineLabels={machineLabels}
          onClose={() => {
            setEditing(null);
          }}
          onSaved={(g) => {
            notify.success(`Geofence ${g.name} saved · area ${formatArea(g.area_m2)}.`);
            setLastSaved(g);
            setSelectedId(g.id);
            geofences.reload();
          }}
        />
      )}
      {creatingSite && (
        <JobSiteDialog
          onClose={() => {
            setCreatingSite(false);
          }}
          onCreated={(s) => {
            notify.success(`Job site ${s.name} created.`);
            sites.reload();
          }}
        />
      )}
    </>
  );
}
