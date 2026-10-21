import { Alert, Box, Button, Stack, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { fleetService } from '../../../api/services/fleetService';
import type { HistoryDto, SiteVisitDto, StopDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { DateTimeField } from '../../../components/forms/DateTimeField';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { formatDuration, formatInstantIn } from '../../../utils/time';
import { HistoryPlayback } from './HistoryPlayback';
import { defaultHistoryRange, validateHistoryRange, type HistoryRange } from './historyRange';

interface HistoryTabProps {
  machineId: string;
  timeZone: string;
  /** Initial window (defaults to the last 24 h). */
  initialRange?: HistoryRange;
}

function stopColumns(tz: string): DataColumn<StopDto>[] {
  return [
    { id: 'start', header: 'Start', render: (s) => formatInstantIn(s.start, tz) },
    { id: 'end', header: 'End', render: (s) => formatInstantIn(s.end, tz) },
    { id: 'dur', header: 'Duration', render: (s) => formatDuration(s.duration_seconds) },
    {
      id: 'pos',
      header: 'Position',
      render: (s) => `${s.latitude.toFixed(5)}, ${s.longitude.toFixed(5)}`,
    },
  ];
}

function visitColumns(tz: string): DataColumn<SiteVisitDto>[] {
  return [
    { id: 'site', header: 'Geofence', render: (v) => v.geofence_name },
    {
      id: 'in',
      header: 'Entered',
      render: (v) => (v.entered_at === null ? 'Before range' : formatInstantIn(v.entered_at, tz)),
    },
    {
      id: 'out',
      header: 'Exited',
      render: (v) => (v.exited_at === null ? 'Still inside' : formatInstantIn(v.exited_at, tz)),
    },
    { id: 'dur', header: 'Time inside', render: (v) => formatDuration(v.duration_seconds) },
  ];
}

function HistoryResult({
  history,
  timeZone,
  queryKey,
}: {
  history: HistoryDto;
  timeZone: string;
  queryKey: string;
}) {
  return (
    <Stack spacing={3}>
      {history.truncated && (
        <Alert severity="warning">
          The range has more points than can be returned at once; only part of the track is shown.
          Narrow the range to see every point.
        </Alert>
      )}
      <KeyValueGrid
        columns={4}
        items={[
          { label: 'Distance', value: `${history.distance_km.toFixed(2)} km` },
          { label: 'Points', value: String(history.points.length) },
          { label: 'Stops', value: String(history.stops.length) },
          { label: 'Policy version', value: history.policy_version },
        ]}
      />
      <HistoryPlayback
        points={history.points}
        stops={history.stops}
        timeZone={timeZone}
        queryKey={queryKey}
      />
      <Box>
        <Typography variant="subtitle1" component="h3" className="mb-1">
          Stops
        </Typography>
        {history.stops.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No stops detected.
          </Typography>
        ) : (
          <StaticTable
            ariaLabel="Stops"
            columns={stopColumns(timeZone)}
            rows={history.stops}
            getRowId={(s) => s.start}
          />
        )}
      </Box>
      <Box>
        <Typography variant="subtitle1" component="h3" className="mb-1">
          Site visits
        </Typography>
        {history.site_visits.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No geofence visits in this range.
          </Typography>
        ) : (
          <StaticTable
            ariaLabel="Site visits"
            columns={visitColumns(timeZone)}
            rows={history.site_visits}
            getRowId={(v) => `${v.geofence_id}-${v.entered_at ?? ''}`}
          />
        )}
      </Box>
    </Stack>
  );
}

/** Route history for a window (≤31 days) with playback, stops and site visits. */
export function HistoryTab({ machineId, timeZone, initialRange }: HistoryTabProps) {
  const [initial] = useState(() => initialRange ?? defaultHistoryRange(Date.now()));
  const [from, setFrom] = useState<string | null>(initial.from);
  const [to, setTo] = useState<string | null>(initial.to);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState<HistoryRange | null>(null);
  const load = useCallback(
    (signal: AbortSignal) =>
      query === null
        ? Promise.reject(new Error('No range selected.'))
        : fleetService.history(machineId, query.from, query.to, signal),
    [machineId, query],
  );
  const history = useAsyncResource(load, [query], query !== null);

  const submit = () => {
    const problem = validateHistoryRange(from, to);
    setError(problem);
    if (problem === null && from !== null && to !== null) setQuery({ from, to });
  };

  return (
    <Stack spacing={3}>
      <Box className="grid grid-cols-1 items-start gap-3 sm:grid-cols-[1fr_1fr_auto]">
        <DateTimeField label="From" value={from} onChange={setFrom} timezone={timeZone} required />
        <DateTimeField label="To" value={to} onChange={setTo} timezone={timeZone} required />
        <Button variant="contained" onClick={submit} sx={{ mt: 1 }}>
          Load history
        </Button>
      </Box>
      {error !== null && <Alert severity="error">{error}</Alert>}
      {query === null ? (
        <EmptyState
          title="Choose a time range"
          description="Load up to 31 days of positions to replay the route."
        />
      ) : (
        <AsyncContent
          resource={history}
          isEmpty={(h) => h.points.length === 0}
          emptyTitle="No positions in this range"
          errorTitle="Could not load history"
          loadingLabel="Loading history"
        >
          {(h) => (
            <HistoryResult history={h} timeZone={timeZone} queryKey={`${query.from}|${query.to}`} />
          )}
        </AsyncContent>
      )}
    </Stack>
  );
}
