import Add from '@mui/icons-material/Add';
import { Box, Button, Paper, Stack, Typography } from '@mui/material';
import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { geofenceService } from '../../../api/services/geofenceService';
import { machineService } from '../../../api/services/machineService';
import type { GeofenceDto, JobSiteDto } from '../../../api/types';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { standardRowActions } from '../../../components/lifecycle/rowActions';
import { ShowInactiveToggle } from '../../../components/lifecycle/ShowInactiveToggle';
import { useLifecycleDialog } from '../../../components/lifecycle/useLifecycleDialog';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useScrollIntoView } from '../../../hooks/useScrollIntoView';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { machineLabel } from '../shared/display';
import { jobSiteLabel } from '../shared/lookups';
import { formatArea } from './geofenceForm';
import { GeofenceDetailsDrawer } from './GeofenceDetailsDrawer';
import { GeofenceDialog } from './GeofenceDialog';
import {
  GEOFENCE_DEACTIVATE_CONSEQUENCES,
  GEOFENCE_ERROR_HINTS,
  JOB_SITE_DEACTIVATE_CONSEQUENCES,
  JOB_SITE_ERROR_HINTS,
} from './geofenceLifecycle';
import { GeofencesMap } from './GeofencesMap';
import { GeofencesTable } from './GeofencesTable';
import { JobSiteDetailsDrawer } from './JobSiteDetailsDrawer';
import { JobSiteDialog } from './JobSiteDialog';
import { JobSitesTable } from './JobSitesTable';

type Editing =
  | { kind: 'new' }
  | { kind: 'edit'; geofence: GeofenceDto }
  | { kind: 'new-site' }
  | { kind: 'edit-site'; site: JobSiteDto }
  | null;
type Viewing = { kind: 'geofence'; id: string } | { kind: 'site'; id: string } | null;

const NO_SITES: readonly JobSiteDto[] = [];
const NO_GEOFENCES: readonly GeofenceDto[] = [];

function SectionTitle({ title, toggle }: { title: string; toggle: ReactNode }) {
  return (
    <Box className="mb-2 flex flex-wrap items-center justify-between gap-2">
      <Typography variant="subtitle1" component="h2">
        {title}
      </Typography>
      {toggle}
    </Box>
  );
}

/** Job sites and geofences with a map preview: view, draw / edit, deactivate / reactivate. */
export function GeofencesPage() {
  const notify = useNotify();
  const { hasPermission } = useSession();
  const canWrite = useCanMutate(PERMISSIONS.tenantGeofenceWrite);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editing, setEditing] = useState<Editing>(null);
  const [viewing, setViewing] = useState<Viewing>(null);
  const [lastSaved, setLastSaved] = useState<GeofenceDto | null>(null);
  const [inactiveFences, setInactiveFences] = useState(false);
  const [inactiveSites, setInactiveSites] = useState(false);

  const loadGeofences = useCallback(
    (signal: AbortSignal) => geofenceService.list(signal, inactiveFences),
    [inactiveFences],
  );
  const geofences = useAsyncResource(loadGeofences, [inactiveFences]);
  const loadSites = useCallback(
    (signal: AbortSignal) => geofenceService.listJobSites(signal, undefined, inactiveSites),
    [inactiveSites],
  );
  const sites = useAsyncResource(loadSites, [inactiveSites]);
  const [params] = useSearchParams();
  /** `?tab=sites` (e.g. from the go-live checklist) opens on the job sites, once both lists loaded. */
  const sitesRef = useScrollIntoView<HTMLDivElement>(
    params.get('tab') === 'sites',
    sites.data !== null && geofences.data !== null,
  );
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
  const fenceList = geofences.data ?? NO_GEOFENCES;
  const siteOf = (id: string | null) =>
    (id === null ? undefined : siteList.find((x) => x.id === id)) ?? null;
  const siteName = (id: string | null) => {
    const s = siteOf(id);
    return s === null ? '—' : jobSiteLabel(s);
  };

  const fenceLifecycle = useLifecycleDialog<GeofenceDto>({
    labelOf: (g) => g.name,
    noun: 'geofence',
    errorHints: GEOFENCE_ERROR_HINTS,
    consequences: GEOFENCE_DEACTIVATE_CONSEQUENCES,
    deactivate: (g, body, key) =>
      geofenceService.deactivate(g.id, { ...body, version: g.version }, key),
    reactivate: (g, body, key) =>
      geofenceService.reactivate(g.id, { ...body, version: g.version }, key),
    onDone: (g, kind) => {
      notify.success(
        `Geofence ${g.name} ${kind === 'deactivate' ? 'deactivated' : 'reactivated'}.`,
      );
      geofences.reload();
    },
    onReload: geofences.reload,
  });
  const siteLifecycle = useLifecycleDialog<JobSiteDto>({
    labelOf: jobSiteLabel,
    noun: 'job site',
    errorHints: JOB_SITE_ERROR_HINTS,
    consequences: JOB_SITE_DEACTIVATE_CONSEQUENCES,
    deactivate: (s, body, key) =>
      geofenceService.deactivateJobSite(s.id, { ...body, version: s.version }, key),
    reactivate: (s, body, key) =>
      geofenceService.reactivateJobSite(s.id, { ...body, version: s.version }, key),
    onDone: (s, kind) => {
      notify.success(
        `Job site ${s.name} ${kind === 'deactivate' ? 'deactivated' : 'reactivated'}.`,
      );
      sites.reload();
    },
    onReload: sites.reload,
  });

  const geofenceActions = (g: GeofenceDto, inDrawer: boolean): RowAction[] => {
    const [view, ...rest] = standardRowActions({
      active: g.is_active,
      canEdit: canWrite,
      canChangeState: canWrite,
      onView: () => {
        setViewing({ kind: 'geofence', id: g.id });
      },
      onEdit: () => {
        setViewing(null);
        setEditing({ kind: 'edit', geofence: g });
      },
      onDeactivate: () => {
        fenceLifecycle.open('deactivate', g);
      },
      onReactivate: () => {
        fenceLifecycle.open('reactivate', g);
      },
    });
    const showOnMap: RowAction = {
      key: 'map',
      label: 'Show on map',
      onClick: () => {
        setSelectedId(g.id);
        if (inDrawer) setViewing(null);
      },
    };
    return [...(view !== undefined && !inDrawer ? [view] : []), showOnMap, ...rest];
  };
  const siteActions = (s: JobSiteDto, inDrawer: boolean): RowAction[] =>
    standardRowActions({
      active: s.is_active,
      canEdit: canWrite,
      canChangeState: canWrite,
      ...(inDrawer
        ? {}
        : {
            onView: () => {
              setViewing({ kind: 'site', id: s.id });
            },
          }),
      onEdit: () => {
        setEditing({ kind: 'edit-site', site: s });
      },
      onDeactivate: () => {
        siteLifecycle.open('deactivate', s);
      },
      onReactivate: () => {
        siteLifecycle.open('reactivate', s);
      },
    });
  const viewedGeofence =
    viewing?.kind === 'geofence' ? (fenceList.find((g) => g.id === viewing.id) ?? null) : null;
  const viewedSite =
    viewing?.kind === 'site' ? (siteList.find((s) => s.id === viewing.id) ?? null) : null;
  const closeEditor = () => {
    setEditing(null);
  };
  const closeViewer = () => {
    setViewing(null);
  };

  return (
    <>
      <PageHeader
        title="Sites & geofences"
        subtitle="Job sites, allowed / restricted areas and corridors"
        actions={
          <CanMutate permission={PERMISSIONS.tenantGeofenceWrite}>
            <Button
              onClick={() => {
                setEditing({ kind: 'new-site' });
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
            <SectionTitle
              title="Geofences"
              toggle={
                <ShowInactiveToggle
                  checked={inactiveFences}
                  onChange={setInactiveFences}
                  label="Show inactive geofences"
                />
              }
            />
            <AsyncContent
              resource={geofences}
              isEmpty={(g) => g.length === 0}
              emptyTitle="No geofences yet"
              emptyDescription="Draw allowed areas, restricted areas or corridors to get location alerts."
            >
              {(rows) => (
                <GeofencesTable
                  rows={rows}
                  siteName={siteName}
                  machineLabels={machineLabels}
                  actionsFor={(g) => geofenceActions(g, false)}
                  onSelect={setSelectedId}
                />
              )}
            </AsyncContent>
          </Paper>
        </Box>
        <Paper
          ref={sitesRef}
          id="job-sites"
          variant="outlined"
          className="p-3"
          sx={{ scrollMarginTop: 80 }}
        >
          <SectionTitle
            title="Job sites"
            toggle={
              <ShowInactiveToggle
                checked={inactiveSites}
                onChange={setInactiveSites}
                label="Show inactive job sites"
              />
            }
          />
          <AsyncContent
            resource={sites}
            isEmpty={(s) => s.length === 0}
            emptyTitle="No job sites yet"
          >
            {(rows) => <JobSitesTable rows={rows} actionsFor={(s) => siteActions(s, false)} />}
          </AsyncContent>
        </Paper>
      </Stack>
      {(editing?.kind === 'new' || editing?.kind === 'edit') && (
        <GeofenceDialog
          {...(editing.kind === 'edit' ? { geofence: editing.geofence } : {})}
          sites={siteList}
          machineLabels={machineLabels}
          onClose={closeEditor}
          onReloadRequested={geofences.reload}
          onSaved={(g) => {
            notify.success(`Geofence ${g.name} saved · area ${formatArea(g.area_m2)}.`);
            setLastSaved(g);
            setSelectedId(g.id);
            geofences.reload();
          }}
        />
      )}
      {(editing?.kind === 'new-site' || editing?.kind === 'edit-site') && (
        <JobSiteDialog
          {...(editing.kind === 'edit-site' ? { site: editing.site } : {})}
          onClose={closeEditor}
          onReloadRequested={sites.reload}
          onSaved={(s) => {
            notify.success(
              `Job site ${s.name} ${editing.kind === 'edit-site' ? 'updated' : 'created'}.`,
            );
            sites.reload();
          }}
        />
      )}
      {viewedGeofence !== null && (
        <GeofenceDetailsDrawer
          geofence={viewedGeofence}
          site={siteOf(viewedGeofence.job_site_id)}
          machineLabels={machineLabels}
          actions={geofenceActions(viewedGeofence, true)}
          onClose={closeViewer}
        />
      )}
      {viewedSite !== null && (
        <JobSiteDetailsDrawer
          site={viewedSite}
          geofences={fenceList}
          actions={siteActions(viewedSite, true)}
          onOpenGeofence={(g) => {
            setViewing({ kind: 'geofence', id: g.id });
          }}
          onClose={closeViewer}
        />
      )}
      {fenceLifecycle.dialog}
      {siteLifecycle.dialog}
    </>
  );
}
