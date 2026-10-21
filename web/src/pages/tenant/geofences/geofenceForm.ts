import { mixed, object, string } from 'yup';
import type { GeofenceDto, GeofenceIn, GeofenceKind, GeofenceShape } from '../../../api/types';
import {
  canComplete,
  lineFromVertices,
  polygonFromVertices,
  verticesFromRing,
} from '../../../components/map/drawing';
import type { LonLat } from '../../../components/map/geo';

export interface MachineOption {
  id: string;
  label: string;
}

export interface GeofenceFormValues {
  name: string;
  kind: GeofenceKind;
  job_site_id: string;
  shape: GeofenceShape;
  vertices: LonLat[];
  /** Polygon ring closed by the user. */
  closed: boolean;
  corridor_width_m: string;
  applies_to: 'ALL' | 'SELECTED';
  machines: MachineOption[];
}

export const EMPTY_GEOFENCE: GeofenceFormValues = {
  name: '',
  kind: 'ALLOWED_AREA',
  job_site_id: '',
  shape: 'POLYGON',
  vertices: [],
  closed: false,
  corridor_width_m: '',
  applies_to: 'ALL',
  machines: [],
};

function isLonLat(v: unknown): v is LonLat {
  return Array.isArray(v) && typeof v[0] === 'number' && typeof v[1] === 'number';
}

/** Vertices of the stored source geometry (Polygon outer ring or corridor LineString). */
export function sourceVertices(source: Record<string, unknown>): LonLat[] {
  const coords = source.coordinates;
  if (!Array.isArray(coords)) return [];
  if (source.type === 'Polygon') {
    const ring: unknown = coords[0];
    return Array.isArray(ring) ? verticesFromRing(ring.filter(isLonLat)) : [];
  }
  if (source.type === 'LineString') return coords.filter(isLonLat).map(([x, y]) => [x, y]);
  return [];
}

export function geofenceToValues(
  g: GeofenceDto,
  machineLabels: ReadonlyMap<string, string>,
): GeofenceFormValues {
  const vertices = sourceVertices(g.source_geometry);
  return {
    name: g.name,
    kind: g.kind,
    job_site_id: g.job_site_id ?? '',
    shape: g.shape,
    vertices,
    closed: g.shape === 'POLYGON' && vertices.length >= 3,
    corridor_width_m: g.corridor_width_m === null ? '' : String(g.corridor_width_m),
    applies_to: g.machine_ids.length === 0 ? 'ALL' : 'SELECTED',
    machines: g.machine_ids.map((id) => ({ id, label: machineLabels.get(id) ?? id })),
  };
}

const DECIMAL = /^\d+(\.\d+)?$/;

type Parent = GeofenceFormValues;

export const geofenceSchema = object({
  name: string().trim().required('Name is required').max(200, 'At most 200 characters'),
  kind: mixed<GeofenceKind>()
    .oneOf(['ALLOWED_AREA', 'RESTRICTED_AREA', 'SITE_BOUNDARY'])
    .required(),
  // Formik hands '' to Yup as undefined, hence the defaults.
  job_site_id: string().default(''),
  shape: mixed<GeofenceShape>().oneOf(['POLYGON', 'CORRIDOR']).required(),
  vertices: mixed<LonLat[]>((v): v is LonLat[] => Array.isArray(v))
    .required()
    .test('shape', function (value) {
      const p = this.parent as Parent;
      if (p.shape === 'POLYGON') {
        if (!canComplete('polygon', value)) {
          return this.createError({ message: 'Click at least 3 points on the map' });
        }
        if (!p.closed) return this.createError({ message: 'Close the ring to finish the polygon' });
        return true;
      }
      return canComplete('line', value) || this.createError({ message: 'Click at least 2 points' });
    }),
  closed: mixed<boolean>().required(),
  corridor_width_m: string()
    .default('')
    .test('width', 'Width must be a number between 0 and 5000 m', function (value) {
      if ((this.parent as Parent).shape !== 'CORRIDOR') return true;
      if (!DECIMAL.test(value)) return false;
      const n = Number(value);
      return n > 0 && n <= 5000;
    }),
  applies_to: mixed<'ALL' | 'SELECTED'>().oneOf(['ALL', 'SELECTED']).required(),
  machines: mixed<MachineOption[]>((v): v is MachineOption[] => Array.isArray(v))
    .required()
    .test('machines', 'Select at least one machine', function (value) {
      return (this.parent as Parent).applies_to === 'ALL' || value.length > 0;
    }),
});

export function toGeofencePayload(v: GeofenceFormValues): GeofenceIn {
  const polygon = v.shape === 'POLYGON';
  return {
    name: v.name.trim(),
    kind: v.kind,
    job_site_id: v.job_site_id === '' ? null : v.job_site_id,
    polygon: polygon ? polygonFromVertices(v.vertices) : null,
    corridor: polygon ? null : lineFromVertices(v.vertices),
    corridor_width_m: polygon ? null : Number(v.corridor_width_m),
    machine_ids: v.applies_to === 'ALL' ? [] : v.machines.map((m) => m.id),
  };
}

/** `850 m²` / `12.35 ha`. */
export function formatArea(m2: number): string {
  if (m2 < 10_000) return `${Math.round(m2).toLocaleString()} m²`;
  return `${(m2 / 10_000).toLocaleString(undefined, { maximumFractionDigits: 2 })} ha`;
}
