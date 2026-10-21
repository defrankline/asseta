import type { Feature, FeatureCollection } from 'geojson';
import { featureCollection, lineFeature, pointFeature, type LonLat } from './geo';

export type DrawMode = 'polygon' | 'line';

export const MIN_POLYGON_VERTICES = 3;
export const MIN_LINE_VERTICES = 2;

function samePosition(a: LonLat, b: LonLat): boolean {
  return a[0] === b[0] && a[1] === b[1];
}

/** A linear ring: the vertices with the first vertex repeated at the end (GeoJSON closed ring). */
export function closeRing(vertices: readonly LonLat[]): LonLat[] {
  const first = vertices[0];
  const last = vertices[vertices.length - 1];
  if (first === undefined || last === undefined) return [];
  return samePosition(first, last) ? [...vertices] : [...vertices, first];
}

/** GeoJSON Polygon (single closed outer ring) from drawn vertices. */
export function polygonFromVertices(vertices: readonly LonLat[]): {
  type: 'Polygon';
  coordinates: LonLat[][];
} {
  return { type: 'Polygon', coordinates: [closeRing(vertices)] };
}

/** GeoJSON LineString (corridor centre line) from drawn vertices. */
export function lineFromVertices(vertices: readonly LonLat[]): {
  type: 'LineString';
  coordinates: LonLat[];
} {
  return { type: 'LineString', coordinates: vertices.map(([x, y]) => [x, y]) };
}

/** Drawn vertices from a stored ring (drops the closing duplicate). */
export function verticesFromRing(ring: readonly LonLat[]): LonLat[] {
  const closed =
    ring.length > 1 && samePosition(ring[0] as LonLat, ring[ring.length - 1] as LonLat);
  return (closed ? ring.slice(0, -1) : ring).map(([x, y]) => [x, y]);
}

export function canComplete(mode: DrawMode, vertices: readonly LonLat[]): boolean {
  return vertices.length >= (mode === 'polygon' ? MIN_POLYGON_VERTICES : MIN_LINE_VERTICES);
}

/** Preview features for the drawing layers. */
export function drawingPreview(
  mode: DrawMode,
  vertices: readonly LonLat[],
  closed: boolean,
): FeatureCollection {
  const features: Feature[] = vertices.map((v, i) => pointFeature(v, { kind: 'vertex', index: i }));
  if (mode === 'polygon' && closed && vertices.length >= MIN_POLYGON_VERTICES) {
    features.unshift({
      type: 'Feature',
      geometry: polygonFromVertices(vertices),
      properties: { kind: 'area' },
    });
  } else if (vertices.length >= 2) {
    features.unshift(lineFeature([...vertices], { kind: 'path' }));
  }
  return featureCollection(features);
}
