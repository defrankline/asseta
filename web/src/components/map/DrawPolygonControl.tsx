import type { AddLayerObject } from 'maplibre-gl';
import { useMemo } from 'react';
import { GeoJsonLayer } from './GeoJsonLayer';
import { drawingPreview, type DrawMode } from './drawing';
import type { LonLat } from './geo';
import { useMapClick } from './useMapClick';

interface DrawPolygonControlProps {
  mode: DrawMode;
  vertices: readonly LonLat[];
  /** Polygon ring closed by the user (no more vertices accepted). */
  closed: boolean;
  onAddVertex: (lngLat: LonLat) => void;
  /** Stroke/fill colour of the drawing. */
  color?: string;
}

const SOURCE = 'draw-preview';

/**
 * Click-to-draw on a MapView with plain MapLibre click handlers: each map click appends a vertex
 * (polygon until the ring is closed; polyline for corridors). State lives in the caller, so undo /
 * clear / close are ordinary state updates.
 */
export function DrawPolygonControl({
  mode,
  vertices,
  closed,
  onAddVertex,
  color = '#2563eb',
}: DrawPolygonControlProps) {
  useMapClick(onAddVertex, !(mode === 'polygon' && closed));
  const data = useMemo(() => drawingPreview(mode, vertices, closed), [mode, vertices, closed]);
  const layers = useMemo<AddLayerObject[]>(
    () => [
      {
        id: `${SOURCE}-fill`,
        type: 'fill',
        source: SOURCE,
        filter: ['==', ['get', 'kind'], 'area'],
        paint: { 'fill-color': color, 'fill-opacity': 0.2 },
      },
      {
        id: `${SOURCE}-line`,
        type: 'line',
        source: SOURCE,
        filter: ['in', ['get', 'kind'], ['literal', ['area', 'path']]],
        paint: { 'line-color': color, 'line-width': 2, 'line-dasharray': [2, 1] },
      },
      {
        id: `${SOURCE}-vertex`,
        type: 'circle',
        source: SOURCE,
        filter: ['==', ['get', 'kind'], 'vertex'],
        paint: {
          'circle-radius': 5,
          'circle-color': '#ffffff',
          'circle-stroke-color': color,
          'circle-stroke-width': 2,
        },
      },
    ],
    [color],
  );
  return <GeoJsonLayer id={SOURCE} data={data} layers={layers} />;
}
