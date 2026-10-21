import type { Feature, FeatureCollection, Geometry, GeoJsonProperties } from 'geojson';

export type LonLat = [number, number];

export function featureCollection<G extends Geometry = Geometry>(
  features: Feature<G>[],
): FeatureCollection<G> {
  return { type: 'FeatureCollection', features };
}

export function pointFeature(position: LonLat, properties: GeoJsonProperties = {}): Feature {
  return { type: 'Feature', geometry: { type: 'Point', coordinates: position }, properties };
}

export function lineFeature(positions: LonLat[], properties: GeoJsonProperties = {}): Feature {
  return { type: 'Feature', geometry: { type: 'LineString', coordinates: positions }, properties };
}

export const EMPTY_COLLECTION: FeatureCollection = featureCollection([]);

function isPosition(value: unknown): value is [number, number, ...number[]] {
  return (
    Array.isArray(value) &&
    value.length >= 2 &&
    typeof value[0] === 'number' &&
    typeof value[1] === 'number'
  );
}

/** Every `[lon, lat]` found in a GeoJSON-like value (for fitting bounds of server geometry). */
export function collectPositions(value: unknown, out: LonLat[] = []): LonLat[] {
  if (isPosition(value)) {
    out.push([value[0], value[1]]);
  } else if (Array.isArray(value)) {
    for (const v of value) collectPositions(v, out);
  } else if (typeof value === 'object' && value !== null) {
    const record = value as Record<string, unknown>;
    if ('coordinates' in record) collectPositions(record.coordinates, out);
    if ('geometry' in record) collectPositions(record.geometry, out);
    if ('features' in record) collectPositions(record.features, out);
    if ('geometries' in record) collectPositions(record.geometries, out);
  }
  return out;
}

const GEOMETRY_TYPES = new Set([
  'Point',
  'MultiPoint',
  'LineString',
  'MultiLineString',
  'Polygon',
  'MultiPolygon',
  'GeometryCollection',
  'Feature',
  'FeatureCollection',
]);

/** Narrow a server `Record<string, unknown>` to GeoJSON when it carries a GeoJSON `type`. */
export function asGeoJson(value: Record<string, unknown>): Feature | FeatureCollection | null {
  const type = value.type;
  if (typeof type !== 'string' || !GEOMETRY_TYPES.has(type)) return null;
  if (type === 'FeatureCollection') return value as unknown as FeatureCollection;
  if (type === 'Feature') return value as unknown as Feature;
  return { type: 'Feature', geometry: value as unknown as Geometry, properties: {} };
}

const EARTH_RADIUS_M = 6_371_008.8;

/** Approximate circle of `radiusM` metres around `[lon, lat]` as a closed polygon ring (display only). */
export function circleFeature(
  center: LonLat,
  radiusM: number,
  properties: GeoJsonProperties = {},
  steps = 64,
): Feature {
  const [lon, lat] = center;
  const latRad = (lat * Math.PI) / 180;
  const ring: LonLat[] = [];
  for (let i = 0; i <= steps; i += 1) {
    const theta = (2 * Math.PI * i) / steps;
    const dLat = ((radiusM * Math.cos(theta)) / EARTH_RADIUS_M) * (180 / Math.PI);
    const dLon =
      ((radiusM * Math.sin(theta)) / (EARTH_RADIUS_M * Math.cos(latRad))) * (180 / Math.PI);
    ring.push([lon + dLon, lat + dLat]);
  }
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties };
}
