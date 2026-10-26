import { Typography } from '@mui/material';
import type { AddLayerObject } from 'maplibre-gl';
import { useMemo } from 'react';
import { FitBounds } from '../../../components/map/FitBounds';
import { GeoJsonLayer } from '../../../components/map/GeoJsonLayer';
import { MapView } from '../../../components/map/MapView';
import {
  circleFeature,
  featureCollection,
  pointFeature,
  type LonLat,
} from '../../../components/map/geo';

const PIN = '#2563eb';

const layers = (id: string): AddLayerObject[] => [
  {
    id: `${id}-accuracy`,
    type: 'fill',
    source: id,
    filter: ['==', ['get', 'role'], 'accuracy'],
    paint: { 'fill-color': PIN, 'fill-opacity': 0.15 },
  },
  {
    id: `${id}-pin`,
    type: 'circle',
    source: id,
    filter: ['==', ['get', 'role'], 'pin'],
    paint: {
      'circle-radius': 7,
      'circle-color': PIN,
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 2,
    },
  },
];

/** Mini map with the check-in's GPS fix and its accuracy circle. */
export function CheckinLocationMap({
  latitude,
  longitude,
  accuracyM,
}: {
  latitude: number;
  longitude: number;
  accuracyM: number | null;
}) {
  const at: LonLat = [longitude, latitude];
  const data = useMemo(
    () =>
      featureCollection([
        ...(accuracyM !== null && accuracyM > 0
          ? [circleFeature([longitude, latitude], accuracyM, { role: 'accuracy' })]
          : []),
        pointFeature([longitude, latitude], { role: 'pin' }),
      ]),
    [latitude, longitude, accuracyM],
  );
  const dLat = Math.max(accuracyM ?? 0, 50) / 111_320;
  return (
    <div>
      <MapView center={at} zoom={15} ariaLabel="Check-in location" className="h-56 w-full rounded">
        <GeoJsonLayer id="site-checkin" data={data} layers={layers('site-checkin')} />
        <FitBounds
          positions={[
            [longitude, latitude - dLat],
            [longitude, latitude + dLat],
          ]}
          fitKey={`${String(latitude)},${String(longitude)},${String(accuracyM)}`}
          maxZoom={17}
        />
      </MapView>
      <Typography variant="caption" color="text.secondary">
        Blue: the phone or browser position when checking in, with its accuracy.
      </Typography>
    </div>
  );
}
