/** TRACKING policy field catalogue (labels/units) and which fields each override scope may set. */

export type FieldKind = 'int' | 'number' | 'nullableNumber' | 'time' | 'weekdays';

export interface PolicyFieldDef {
  key: string;
  label: string;
  kind: FieldKind;
  unit?: string;
  help?: string;
}

export const TRACKING_FIELDS: readonly PolicyFieldDef[] = [
  { key: 'live_max_age_seconds', label: 'Live max age', kind: 'int', unit: 's' },
  { key: 'stale_after_seconds', label: 'Stale after', kind: 'int', unit: 's' },
  { key: 'offline_after_seconds', label: 'Offline after', kind: 'int', unit: 's' },
  { key: 'max_position_accuracy_m', label: 'Max position accuracy', kind: 'number', unit: 'm' },
  { key: 'geofence_tolerance_m', label: 'Geofence tolerance', kind: 'number', unit: 'm' },
  { key: 'moving_speed_kmh', label: 'Moving speed threshold', kind: 'number', unit: 'km/h' },
  { key: 'stop_min_seconds', label: 'Minimum stop duration', kind: 'int', unit: 's' },
  { key: 'max_plausible_speed_kmh', label: 'Max plausible speed', kind: 'number', unit: 'km/h' },
  {
    key: 'future_timestamp_tolerance_seconds',
    label: 'Future timestamp tolerance',
    kind: 'int',
    unit: 's',
  },
  { key: 'max_replay_age_days', label: 'Max replay age', kind: 'int', unit: 'days' },
  {
    key: 'low_power_voltage',
    label: 'Low power voltage',
    kind: 'nullableNumber',
    unit: 'V',
    help: 'Leave empty to disable low-power alerts.',
  },
  {
    key: 'operating_window_start',
    label: 'Operating window start',
    kind: 'time',
    help: 'Tenant local time; leave both start and end empty for no window.',
  },
  { key: 'operating_window_end', label: 'Operating window end', kind: 'time' },
  { key: 'operating_weekdays', label: 'Operating weekdays', kind: 'weekdays' },
];

export type OverrideScope = 'TENANT' | 'MACHINE' | 'SITE';

/** Fields a lower scope may override (mirrors the backend OVERRIDABLE table; tenant = all). */
const SCOPE_FIELDS: Readonly<Record<Exclude<OverrideScope, 'TENANT'>, ReadonlySet<string>>> = {
  MACHINE: new Set([
    'live_max_age_seconds',
    'stale_after_seconds',
    'offline_after_seconds',
    'max_position_accuracy_m',
    'low_power_voltage',
    'max_plausible_speed_kmh',
    'operating_window_start',
    'operating_window_end',
    'operating_weekdays',
  ]),
  SITE: new Set(['geofence_tolerance_m']),
};

export function allowedFields(scope: OverrideScope): readonly PolicyFieldDef[] {
  if (scope === 'TENANT') return TRACKING_FIELDS;
  const allowed = SCOPE_FIELDS[scope];
  return TRACKING_FIELDS.filter((f) => allowed.has(f.key));
}

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const;

/** Human display of a policy value. */
export function formatPolicyValue(def: PolicyFieldDef | undefined, value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (def?.kind === 'weekdays' && Array.isArray(value)) {
    return value
      .map((d) => (typeof d === 'number' ? (WEEKDAYS[d] ?? String(d)) : String(d)))
      .join(', ');
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    const text = String(value);
    return def?.unit !== undefined ? `${text} ${def.unit}` : text;
  }
  return JSON.stringify(value);
}

/** Policy value → form input string. */
export function toInputValue(def: PolicyFieldDef, value: unknown): string {
  if (value === null || value === undefined) return '';
  if (def.kind === 'weekdays') return Array.isArray(value) ? value.map(String).join(',') : '';
  if (def.kind === 'time' && typeof value === 'string') return value.slice(0, 5);
  return typeof value === 'number' || typeof value === 'string' ? String(value) : '';
}

/** Form input string → API value (input already validated). */
export function fromInputValue(def: PolicyFieldDef, input: string): unknown {
  const v = input.trim();
  switch (def.kind) {
    case 'int':
    case 'number':
      return Number(v);
    case 'nullableNumber':
      return v === '' ? null : Number(v);
    case 'time':
      return v === '' ? null : v;
    case 'weekdays':
      return v === ''
        ? []
        : v
            .split(',')
            .map(Number)
            .sort((a, b) => a - b);
  }
}

/** Client-side shape check only; ranges/ordering are validated by the API (POLICY_INVALID). */
export function inputError(def: PolicyFieldDef, input: string): string | null {
  const v = input.trim();
  switch (def.kind) {
    case 'int':
      return /^\d+$/.test(v) ? null : 'Enter a whole number';
    case 'number':
      return /^\d+(\.\d+)?$/.test(v) ? null : 'Enter a number';
    case 'nullableNumber':
      return v === '' || /^\d+(\.\d+)?$/.test(v) ? null : 'Enter a number or leave empty';
    case 'time':
      return v === '' || /^([01]\d|2[0-3]):[0-5]\d$/.test(v) ? null : 'Use HH:MM (24 h)';
    case 'weekdays':
      return v === '' ? 'Select at least one day' : null;
  }
}
