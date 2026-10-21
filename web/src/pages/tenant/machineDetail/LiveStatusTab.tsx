import Refresh from '@mui/icons-material/Refresh';
import { Box, Button, Paper } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { fleetService } from '../../../api/services/fleetService';
import { FleetMarkersLayer } from '../../../components/fleet/FleetMarkersLayer';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { FitBounds } from '../../../components/map/FitBounds';
import type { LonLat } from '../../../components/map/geo';
import { MapView } from '../../../components/map/MapView';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useInterval } from '../../../hooks/useInterval';
import { useNow } from '../../../hooks/useNow';
import { MachineStatusPanel } from '../fleet/MachineStatusPanel';
import { FLEET_REFRESH_MS } from '../fleet/fleetFilter';
import { DEFAULT_MAP_CENTER } from '../shared/display';

interface LiveStatusTabProps {
  machineId: string;
  timeZone: string;
}

/** Current status evidence for one machine with a mini map; refreshed every 30 s. */
export function LiveStatusTab({ machineId, timeZone }: LiveStatusTabProps) {
  const now = useNow(15_000);
  const [selected, setSelected] = useState<string | null>(null);
  const load = useCallback(
    (signal: AbortSignal) => fleetService.machineStatus(machineId, signal),
    [machineId],
  );
  const status = useAsyncResource(load);
  useInterval(status.reload, FLEET_REFRESH_MS);
  const machines = useMemo(() => (status.data === null ? [] : [status.data]), [status.data]);
  const positions = useMemo<LonLat[]>(
    () =>
      machines.flatMap((m) =>
        m.longitude === null || m.latitude === null ? [] : [[m.longitude, m.latitude] as LonLat],
      ),
    [machines],
  );

  return (
    <AsyncContent resource={status} errorTitle="Could not load live status">
      {(m) => (
        <Box className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Box>
            <Box className="mb-2 flex justify-end">
              <Button size="small" startIcon={<Refresh />} onClick={status.reload}>
                Refresh
              </Button>
            </Box>
            <MachineStatusPanel machine={m} now={now} timeZone={timeZone} />
          </Box>
          <Paper variant="outlined" className="overflow-hidden">
            <MapView
              center={DEFAULT_MAP_CENTER}
              ariaLabel="Machine position"
              className="h-80 w-full"
            >
              <FleetMarkersLayer machines={machines} selectedId={selected} onSelect={setSelected} />
              <FitBounds positions={positions} fitKey={m.machine_id} />
            </MapView>
          </Paper>
        </Box>
      )}
    </AsyncContent>
  );
}
