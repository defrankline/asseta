/**
 * Policy field catalogues (labels/units/kinds) per policy type and which fields each override scope may
 * set (mirrors the backend OVERRIDABLE table; tenant = all fields).
 */
import type { PolicyType } from '../../../api/types';

/** `decimal` values stay strings end to end (never parsed to float). */
export type FieldKind =
  'int' | 'number' | 'nullableNumber' | 'decimal' | 'time' | 'weekdays' | 'bool' | 'enum';

export interface FieldOption {
  value: string;
  label: string;
}

export interface PolicyFieldDef {
  key: string;
  label: string;
  kind: FieldKind;
  unit?: string;
  help?: string;
  /** Allowed values for `enum` fields. */
  options?: readonly FieldOption[];
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

const CAPTURE_MODES: readonly FieldOption[] = [
  { value: 'AUTOMATIC', label: 'Automatic (photo + on-device OCR)' },
  { value: 'MANUAL', label: 'Manual (numeric entry)' },
];

export const METER_CAPTURE_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'opening_mode',
    label: 'Opening reading mode',
    kind: 'enum',
    options: CAPTURE_MODES,
    help: 'Set independently of the closing mode.',
  },
  {
    key: 'closing_mode',
    label: 'Closing reading mode',
    kind: 'enum',
    options: CAPTURE_MODES,
    help: 'Set independently of the opening mode.',
  },
  { key: 'manual_photo_required', label: 'Photo required for manual readings', kind: 'bool' },
  {
    key: 'min_ocr_confidence',
    label: 'Minimum OCR confidence',
    kind: 'number',
    help: 'Between 0 and 1.',
  },
  { key: 'max_recapture_attempts', label: 'Max recapture attempts', kind: 'int' },
  {
    key: 'manual_correction_requires_review',
    label: 'OCR corrections require review',
    kind: 'bool',
  },
  {
    key: 'gps_enforcement',
    label: 'GPS enforcement',
    kind: 'enum',
    options: [
      { value: 'SOFT', label: 'Soft — keep as provisional for review' },
      { value: 'HARD', label: 'Hard — reject the reading' },
    ],
    help: 'What happens when a reading has no valid GPS fix.',
  },
  { key: 'gps_max_accuracy_m', label: 'GPS max accuracy', kind: 'number', unit: 'm' },
  { key: 'gps_max_age_seconds', label: 'GPS max fix age', kind: 'int', unit: 's' },
  {
    key: 'tracker_comparison_window_seconds',
    label: 'Tracker comparison window',
    kind: 'int',
    unit: 's',
  },
  {
    key: 'tracker_distance_tolerance_m',
    label: 'Tracker distance tolerance',
    kind: 'number',
    unit: 'm',
  },
  {
    key: 'max_hours_per_elapsed_hour',
    label: 'Max meter hours per elapsed hour',
    kind: 'decimal',
  },
  { key: 'continuity_tolerance_hours', label: 'Continuity tolerance', kind: 'decimal', unit: 'h' },
  {
    key: 'telemetry_engine_hours_tolerance',
    label: 'Telemetry engine-hours tolerance',
    kind: 'decimal',
    unit: 'h',
  },
];

export const HIRE_BILLING_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'billable_hours_increment',
    label: 'Billable hours increment',
    kind: 'decimal',
    unit: 'h',
    help: 'Billable hours are rounded to multiples of this (e.g. 0.1).',
  },
  {
    key: 'rounding',
    label: 'Rounding',
    kind: 'enum',
    options: [
      { value: 'UP', label: 'Up' },
      { value: 'HALF_UP', label: 'Half up' },
      { value: 'DOWN', label: 'Down' },
    ],
  },
];

export const DEVICE_SYNC_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'offline_grant_hours',
    label: 'Offline grant',
    kind: 'int',
    unit: 'h',
    help: 'How long a field device may keep working without contacting the server.',
  },
  {
    key: 'snapshot_validity_hours',
    label: 'Policy snapshot validity',
    kind: 'int',
    unit: 'h',
    help: 'Cached capture rules expire after this and must be refreshed.',
  },
  { key: 'max_batch_operations', label: 'Max operations per sync batch', kind: 'int' },
  { key: 'clock_skew_alert_seconds', label: 'Device clock skew alert', kind: 'int', unit: 's' },
];

export const POLICY_FIELDS: Readonly<Record<PolicyType, readonly PolicyFieldDef[]>> = {
  TRACKING: TRACKING_FIELDS,
  METER_CAPTURE: METER_CAPTURE_FIELDS,
  HIRE_BILLING: HIRE_BILLING_FIELDS,
  DEVICE_SYNC: DEVICE_SYNC_FIELDS,
};

export const POLICY_TYPE_LABELS: Readonly<Record<PolicyType, string>> = {
  TRACKING: 'Tracking',
  METER_CAPTURE: 'Meter capture',
  HIRE_BILLING: 'Hire billing',
  DEVICE_SYNC: 'Device sync',
};

export type OverrideScope = 'TENANT' | 'MACHINE' | 'SITE';

type LowerScope = Exclude<OverrideScope, 'TENANT'>;

/** Fields a lower scope may override (mirrors the backend OVERRIDABLE table; tenant = all). */
const SCOPE_FIELDS: Readonly<
  Record<PolicyType, Readonly<Record<LowerScope, ReadonlySet<string>>> | null>
> = {
  TRACKING: {
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
  },
  METER_CAPTURE: {
    MACHINE: new Set([
      'opening_mode',
      'closing_mode',
      'manual_photo_required',
      'min_ocr_confidence',
      'max_hours_per_elapsed_hour',
      'telemetry_engine_hours_tolerance',
    ]),
    SITE: new Set(['gps_max_accuracy_m', 'tracker_distance_tolerance_m']),
  },
  // Hire billing is tenant-wide only.
  HIRE_BILLING: null,
  DEVICE_SYNC: null,
};

/** Scopes at which a tenant may version this policy type. */
export function scopesFor(ptype: PolicyType): readonly OverrideScope[] {
  return SCOPE_FIELDS[ptype] === null ? ['TENANT'] : ['TENANT', 'MACHINE', 'SITE'];
}

export function allowedFields(ptype: PolicyType, scope: OverrideScope): readonly PolicyFieldDef[] {
  const all = POLICY_FIELDS[ptype];
  if (scope === 'TENANT') return all;
  const allowed = SCOPE_FIELDS[ptype]?.[scope];
  return allowed === undefined ? [] : all.filter((f) => allowed.has(f.key));
}

export function findField(ptype: PolicyType, key: string): PolicyFieldDef | undefined {
  return POLICY_FIELDS[ptype].find((f) => f.key === key);
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
  if (def?.kind === 'bool' && typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (def?.kind === 'enum' && typeof value === 'string') {
    return def.options?.find((o) => o.value === value)?.label ?? value;
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
  if (def.kind === 'bool') return value === true ? 'true' : 'false';
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
    case 'decimal':
    case 'enum':
      return v;
    case 'bool':
      return v === 'true';
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
    case 'decimal':
      return /^\d+(\.\d+)?$/.test(v) ? null : 'Enter a decimal number';
    case 'bool':
      return v === 'true' || v === 'false' ? null : 'Choose yes or no';
    case 'enum':
      return def.options?.some((o) => o.value === v) === true ? null : 'Choose a value';
  }
}
