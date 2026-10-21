import type { FeatureCollection } from 'geojson';
import type { AddLayerObject } from 'maplibre-gl';
import type { StopDto, TrackPointDto } from '../../../api/types';
import {
  featureCollection,
  lineFeature,
  pointFeature,
  type LonLat,
} from '../../../components/map/geo';

export const ROUTE_SOURCE = 'history-route';
export const STOPS_SOURCE = 'history-stops';
export const PLAYBACK_SOURCE = 'history-playback';

export const HISTORY_COLORS = {
  route: '#2563eb',
  normal: '#2563eb',
  late: '#9333ea',
  lowQuality: '#ea580c',
  stop: '#111827',
  playback: '#dc2626',
} as const;

export function isLowQuality(p: TrackPointDto): boolean {
  return p.quality !== 'GOOD';
}

/** Route polyline + every point, flagged late / low quality for distinct styling. */
export function routeData(points: readonly TrackPointDto[]): FeatureCollection {
  const coords: LonLat[] = points.map((p) => [p.longitude, p.latitude]);
  return featureCollection([
    ...(coords.length >= 2 ? [lineFeature(coords, { kind: 'route' })] : []),
    ...points.map((p, i) =>
      pointFeature([p.longitude, p.latitude], {
        kind: 'point',
        index: i,
        late: p.is_late,
        lowQuality: isLowQuality(p),
      }),
    ),
  ]);
}

export function stopsData(stops: readonly StopDto[]): FeatureCollection {
  return featureCollection(
    stops.map((s) => pointFeature([s.longitude, s.latitude], { kind: 'stop', start: s.start })),
  );
}

export function playbackData(point: TrackPointDto | undefined): FeatureCollection {
  return featureCollection(
    point === undefined
      ? []
      : [pointFeature([point.longitude, point.latitude], { kind: 'playback' })],
  );
}

export const ROUTE_LAYERS: AddLayerObject[] = [
  {
    id: `${ROUTE_SOURCE}-line`,
    type: 'line',
    source: ROUTE_SOURCE,
    filter: ['==', ['get', 'kind'], 'route'],
    paint: { 'line-color': HISTORY_COLORS.route, 'line-width': 3, 'line-opacity': 0.7 },
  },
  {
    id: `${ROUTE_SOURCE}-points`,
    type: 'circle',
    source: ROUTE_SOURCE,
    filter: ['==', ['get', 'kind'], 'point'],
    paint: {
      'circle-radius': ['case', ['any', ['get', 'late'], ['get', 'lowQuality']], 5, 3],
      'circle-color': [
        'case',
        ['get', 'lowQuality'],
        '#ffffff',
        ['get', 'late'],
        HISTORY_COLORS.late,
        HISTORY_COLORS.normal,
      ],
      'circle-stroke-color': [
        'case',
        ['get', 'lowQuality'],
        HISTORY_COLORS.lowQuality,
        ['get', 'late'],
        HISTORY_COLORS.late,
        HISTORY_COLORS.normal,
      ],
      'circle-stroke-width': ['case', ['get', 'lowQuality'], 2, 1],
    },
  },
];

export const STOP_LAYERS: AddLayerObject[] = [
  {
    id: `${STOPS_SOURCE}-circle`,
    type: 'circle',
    source: STOPS_SOURCE,
    paint: {
      'circle-radius': 8,
      'circle-color': HISTORY_COLORS.stop,
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 2,
    },
  },
];

export const PLAYBACK_LAYERS: AddLayerObject[] = [
  {
    id: `${PLAYBACK_SOURCE}-marker`,
    type: 'circle',
    source: PLAYBACK_SOURCE,
    paint: {
      'circle-radius': 9,
      'circle-color': HISTORY_COLORS.playback,
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 3,
    },
  },
];
