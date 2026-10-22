import Refresh from '@mui/icons-material/Refresh';
import { Box, Button, Paper, Typography } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { fleetService } from '../../../api/services/fleetService';
import type { MachineMapDto } from '../../../api/types';
import { AgeText } from '../../../components/display/AgeText';
import { ConnectivityLegend } from '../../../components/fleet/ConnectivityLegend';
import { FleetMarkersLayer } from '../../../components/fleet/FleetMarkersLayer';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { ErrorState } from '../../../components/feedback/ErrorState';
import { LoadingState } from '../../../components/feedback/LoadingState';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { FitBounds } from '../../../components/map/FitBounds';
import type { LonLat } from '../../../components/map/geo';
import { MapView } from '../../../components/map/MapView';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useInterval } from '../../../hooks/useInterval';
import { useNow } from '../../../hooks/useNow';
import { formatInstantIn } from '../../../utils/time';
import { DEFAULT_MAP_CENTER } from '../shared/display';
import { FleetMachineList } from './FleetMachineList';
import { filterFleet, FLEET_REFRESH_MS, type ConnectivityFilter } from './fleetFilter';
import { MachineStatusPanel } from './MachineStatusPanel';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';

interface FleetSnapshot {
  items: MachineMapDto[];
  fetchedAt: string;
}

function FleetView({
  snapshot,
  now,
  timeZone,
}: {
  snapshot: FleetSnapshot;
  now: number;
  timeZone: string;
}) {
  const [search, setSearch] = useState('');
  const [connectivity, setConnectivity] = useState<ConnectivityFilter>('ALL');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const visible = useMemo(
    () => filterFleet(snapshot.items, search, connectivity),
    [snapshot.items, search, connectivity],
  );
  const positions = useMemo<LonLat[]>(
    () =>
      snapshot.items.flatMap((m) =>
        m.longitude === null || m.latitude === null ? [] : [[m.longitude, m.latitude] as LonLat],
      ),
    [snapshot.items],
  );
  const selected = snapshot.items.find((m) => m.machine_id === selectedId) ?? null;

  if (snapshot.items.length === 0) {
    return (
      <EmptyState
        title="No machines yet"
        description="Register machines and assign trackers to see them on the map."
      />
    );
  }
  return (
    <Box className="grid grid-cols-1 gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
      <FleetMachineList
        all={snapshot.items}
        machines={visible}
        search={search}
        onSearch={setSearch}
        connectivity={connectivity}
        onConnectivity={setConnectivity}
        selectedId={selectedId}
        onSelect={setSelectedId}
        now={now}
        timeZone={timeZone}
      />
      <Box className="flex min-w-0 flex-col gap-3">
        <Paper variant="outlined" className="overflow-hidden">
          <MapView
            center={DEFAULT_MAP_CENTER}
            zoom={6}
            ariaLabel="Fleet map"
            className="h-[28rem] w-full"
          >
            <FleetMarkersLayer
              machines={visible}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
            <FitBounds positions={positions} fitKey="initial" />
          </MapView>
        </Paper>
        <ConnectivityLegend />
        <Paper variant="outlined" className="p-3">
          {selected === null ? (
            <Typography variant="body2" color="text.secondary">
              Select a machine on the map or in the list to see its status evidence.
            </Typography>
          ) : (
            <MachineStatusPanel machine={selected} now={now} timeZone={timeZone} linkToDetail />
          )}
        </Paper>
      </Box>
    </Box>
  );
}

/** Fleet command map: near-live / last-known positions, refreshed every 30 s. */
export function FleetMapPage() {
  const timeZone = useDisplayTimeZone();
  const now = useNow(15_000);
  const load = useCallback(async (signal: AbortSignal): Promise<FleetSnapshot> => {
    const items = await fleetService.map(signal);
    return { items, fetchedAt: new Date().toISOString() };
  }, []);
  const fleet = useAsyncResource(load);
  useInterval(fleet.reload, FLEET_REFRESH_MS);
  // Positions and alerts are also pushed; the interval stays as a fallback.
  useLiveRefresh([ENTITY.fleetPosition, ENTITY.alert], fleet.reload, { debounceMs: 1500 });
  const fetchedAt = fleet.data?.fetchedAt ?? null;

  return (
    <>
      <PageHeader
        title="Fleet map"
        subtitle="Live and last-known machine positions with status evidence"
        actions={
          <Box className="flex items-center gap-2">
            <Typography variant="body2" color="text.secondary" aria-live="polite">
              {fetchedAt === null ? (
                'Loading…'
              ) : (
                <>
                  Updated at {formatInstantIn(fetchedAt, timeZone, true)} (
                  <AgeText at={fetchedAt} now={now} timeZone={timeZone} />)
                </>
              )}
            </Typography>
            <Button
              startIcon={<Refresh />}
              onClick={fleet.reload}
              loading={fleet.loading && fleet.data !== null}
            >
              Refresh
            </Button>
          </Box>
        }
      />
      {fleet.data === null ? (
        fleet.error !== null ? (
          <ErrorState
            error={fleet.error}
            title="Could not load the fleet map"
            onRetry={fleet.reload}
          />
        ) : (
          <LoadingState label="Loading fleet" />
        )
      ) : (
        <>
          {fleet.error !== null && (
            <Box className="mb-3">
              <ErrorState
                error={fleet.error}
                title="Refresh failed — showing the previous snapshot"
                onRetry={fleet.reload}
              />
            </Box>
          )}
          <FleetView snapshot={fleet.data} now={now} timeZone={timeZone} />
        </>
      )}
    </>
  );
}
