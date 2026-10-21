import { Typography } from '@mui/material';
import type { AddLayerObject } from 'maplibre-gl';
import { useMemo } from 'react';
import { FitBounds } from '../map/FitBounds';
import { GeoJsonLayer } from '../map/GeoJsonLayer';
import type { LonLat } from '../map/geo';
import { captureLocationFeatures, type TrackerPosition } from './captureLocation';
import { MapView } from '../map/MapView';

interface CaptureLocationMapProps {
  sourceId: string;
  latitude: number;
  longitude: number;
  accuracyM: number | null;
  /** Allowed phone ↔ tracker distance from the comparison, when compared. */
  allowedM: number | null;
  /** Machine tracker position at the same observation time, when compared. */
  tracker: TrackerPosition | null;
}

const PHONE = '#2563eb';
const TRACKER = '#16a34a';

const layers = (id: string): AddLayerObject[] => [
  {
    id: `${id}-phone-accuracy`,
    type: 'fill',
    source: id,
    filter: ['==', ['get', 'role'], 'phone-accuracy'],
    paint: { 'fill-color': PHONE, 'fill-opacity': 0.15 },
  },
  {
    id: `${id}-tracker-accuracy`,
    type: 'fill',
    source: id,
    filter: ['==', ['get', 'role'], 'tracker-accuracy'],
    paint: { 'fill-color': TRACKER, 'fill-opacity': 0.15 },
  },
  {
    id: `${id}-allowed`,
    type: 'line',
    source: id,
    filter: ['==', ['get', 'role'], 'allowed'],
    paint: { 'line-color': '#d97706', 'line-width': 2, 'line-dasharray': [2, 2] },
  },
  {
    id: `${id}-link`,
    type: 'line',
    source: id,
    filter: ['==', ['get', 'role'], 'link'],
    paint: { 'line-color': '#6b7280', 'line-width': 1.5 },
  },
  {
    id: `${id}-points`,
    type: 'circle',
    source: id,
    filter: ['in', ['get', 'role'], ['literal', ['phone', 'tracker']]],
    paint: {
      'circle-radius': 7,
      'circle-color': ['match', ['get', 'role'], 'tracker', TRACKER, PHONE],
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 2,
    },
  },
];

/** Mini map: phone fix and machine tracker position at the same time, with the allowed ring. */
export function CaptureLocationMap({
  sourceId,
  latitude,
  longitude,
  accuracyM,
  allowedM,
  tracker,
}: CaptureLocationMapProps) {
  const center: LonLat = [longitude, latitude];
  const tLat = tracker?.latitude ?? null;
  const tLon = tracker?.longitude ?? null;
  const tAcc = tracker?.accuracyM ?? null;
  const data = useMemo(
    () =>
      captureLocationFeatures(
        [longitude, latitude],
        accuracyM,
        allowedM,
        tLat === null || tLon === null
          ? null
          : { latitude: tLat, longitude: tLon, accuracyM: tAcc },
      ),
    [latitude, longitude, accuracyM, allowedM, tLat, tLon, tAcc],
  );
  const radius = Math.max(accuracyM ?? 0, allowedM ?? 0, 50);
  const dLat = radius / 111_320;
  const positions: [number, number][] = [
    [longitude, latitude - dLat],
    [longitude, latitude + dLat],
    ...(tracker !== null ? [[tracker.longitude, tracker.latitude] as [number, number]] : []),
  ];
  return (
    <div>
      <MapView
        center={center}
        zoom={15}
        ariaLabel="Reading location"
        className="h-48 w-full rounded"
      >
        <GeoJsonLayer id={sourceId} data={data} layers={layers(sourceId)} />
        <FitBounds
          positions={positions}
          fitKey={`${String(latitude)},${String(longitude)},${String(radius)},${String(tracker?.latitude)},${String(tracker?.longitude)}`}
          maxZoom={17}
        />
      </MapView>
      <Typography variant="caption" color="text.secondary">
        Blue: phone fix and its accuracy.{' '}
        {tracker !== null
          ? 'Green: machine tracker position at the same time and its accuracy. '
          : 'No tracker position was available for comparison. '}
        Dashed ring: allowed phone ↔ tracker distance.
      </Typography>
    </div>
  );
}
