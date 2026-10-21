import Pause from '@mui/icons-material/Pause';
import PlayArrow from '@mui/icons-material/PlayArrow';
import { Box, Chip, IconButton, Paper, Slider, Stack, Typography } from '@mui/material';
import { useMemo, useState } from 'react';
import type { StopDto, TrackPointDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FitBounds } from '../../../components/map/FitBounds';
import { GeoJsonLayer } from '../../../components/map/GeoJsonLayer';
import type { LonLat } from '../../../components/map/geo';
import { MapView } from '../../../components/map/MapView';
import { useInterval } from '../../../hooks/useInterval';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import { DEFAULT_MAP_CENTER } from '../shared/display';
import {
  HISTORY_COLORS,
  isLowQuality,
  PLAYBACK_LAYERS,
  PLAYBACK_SOURCE,
  playbackData,
  ROUTE_LAYERS,
  ROUTE_SOURCE,
  routeData,
  STOP_LAYERS,
  STOPS_SOURCE,
  stopsData,
} from './historyLayers';

interface HistoryPlaybackProps {
  points: readonly TrackPointDto[];
  stops: readonly StopDto[];
  timeZone: string;
  /** Changes when a new history query is loaded (refits the map). */
  queryKey: string;
}

export const PLAYBACK_STEP_MS = 500;

function Swatch({
  color,
  hollow = false,
  label,
}: {
  color: string;
  hollow?: boolean;
  label: string;
}) {
  return (
    <Box component="li" className="flex items-center gap-1">
      <Box
        aria-hidden
        sx={{
          width: 12,
          height: 12,
          borderRadius: '50%',
          border: `2px solid ${color}`,
          bgcolor: hollow ? 'transparent' : color,
        }}
      />
      <Typography variant="caption">{label}</Typography>
    </Box>
  );
}

/** Route map with stops and a slider-driven playback marker through the track points. */
export function HistoryPlayback({ points, stops, timeZone, queryKey }: HistoryPlaybackProps) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const last = Math.max(0, points.length - 1);
  const current = points[Math.min(index, last)];
  const route = useMemo(() => routeData(points), [points]);
  const stopFeatures = useMemo(() => stopsData(stops), [stops]);
  const playback = useMemo(() => playbackData(current), [current]);
  const positions = useMemo<LonLat[]>(() => points.map((p) => [p.longitude, p.latitude]), [points]);

  useInterval(
    () => {
      setIndex((i) => {
        if (i >= last) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    },
    PLAYBACK_STEP_MS,
    playing,
  );

  return (
    <Stack spacing={2}>
      <Paper variant="outlined" className="overflow-hidden">
        <MapView center={DEFAULT_MAP_CENTER} ariaLabel="History map" className="h-96 w-full">
          <GeoJsonLayer id={ROUTE_SOURCE} data={route} layers={ROUTE_LAYERS} />
          <GeoJsonLayer id={STOPS_SOURCE} data={stopFeatures} layers={STOP_LAYERS} />
          <GeoJsonLayer id={PLAYBACK_SOURCE} data={playback} layers={PLAYBACK_LAYERS} />
          <FitBounds positions={positions} fitKey={queryKey} />
        </MapView>
      </Paper>
      <Box
        component="ul"
        aria-label="History legend"
        className="m-0 flex list-none flex-wrap gap-4 p-0"
      >
        <Swatch color={HISTORY_COLORS.normal} label="Point" />
        <Swatch color={HISTORY_COLORS.late} label="Late (buffered/replayed)" />
        <Swatch
          color={HISTORY_COLORS.lowQuality}
          hollow
          label="Low quality (excluded from decisions)"
        />
        <Swatch color={HISTORY_COLORS.stop} label="Stop" />
        <Swatch color={HISTORY_COLORS.playback} label="Playback position" />
      </Box>
      {current !== undefined && (
        <Paper variant="outlined" className="p-3">
          <Box className="flex items-center gap-3">
            <IconButton
              aria-label={playing ? 'Pause playback' : 'Play'}
              onClick={() => {
                if (!playing && index >= last) setIndex(0);
                setPlaying((p) => !p);
              }}
              disabled={points.length < 2}
            >
              {playing ? <Pause /> : <PlayArrow />}
            </IconButton>
            <Slider
              aria-label="Playback position"
              min={0}
              max={last}
              step={1}
              value={Math.min(index, last)}
              disabled={points.length < 2}
              onChange={(_e, v) => {
                setPlaying(false);
                setIndex(v);
              }}
            />
          </Box>
          <Box className="mb-2 flex flex-wrap items-center gap-2">
            <Typography variant="subtitle2">
              Point {Math.min(index, last) + 1} of {points.length}
            </Typography>
            {current.is_late && <Chip size="small" color="secondary" label="Late" />}
            {isLowQuality(current) && (
              <Chip size="small" color="warning" variant="outlined" label="Low quality" />
            )}
          </Box>
          <KeyValueGrid
            columns={4}
            items={[
              { label: 'Event time', value: formatInstantIn(current.event_time, timeZone, true) },
              { label: 'Received', value: formatInstantIn(current.received_at, timeZone, true) },
              {
                label: 'Speed',
                value: current.speed_kmh === null ? '—' : `${current.speed_kmh.toFixed(1)} km/h`,
              },
              {
                label: 'Accuracy',
                value:
                  current.accuracy_m === null
                    ? '—'
                    : `± ${String(Math.round(current.accuracy_m))} m`,
              },
              { label: 'Quality', value: humanize(current.quality) },
              {
                label: 'Ignition',
                value: current.ignition === null ? 'Unknown' : current.ignition ? 'On' : 'Off',
              },
            ]}
          />
        </Paper>
      )}
    </Stack>
  );
}
