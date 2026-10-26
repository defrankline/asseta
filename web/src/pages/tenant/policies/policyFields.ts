/**
 * Policy field catalogues (labels/units/kinds) per policy type and which fields each override scope may
 * set (mirrors the backend OVERRIDABLE table; tenant = all fields).
 */
import type { PolicyType } from '../../../api/types';
import { CASH_CUSTODY_FIELDS, OVERSIGHT_FIELDS } from './accountabilityPolicyFields';
import { CUSTOMER_HOURS_FIELDS } from './customerHoursPolicyFields';
import { ENGINE_HOURS_FIELDS } from './engineHoursPolicyFields';
import { REVENUE_RECONCILIATION_FIELDS } from './revenuePolicyFields';
import { FRAUD_CONTROLS_FIELDS } from './riskPolicyFields';

/** `decimal` values stay strings end to end (never parsed to float). */
export type FieldKind =
  | 'int'
  | 'number'
  | 'nullableNumber'
  | 'decimal'
  | 'nullableDecimal'
  | 'time'
  | 'weekdays'
  | 'bool'
  | 'enum'
  /** A list of values from `options` (e.g. allowed billing modes); stored as a JSON array. */
  | 'multiEnum'
  /** A list of tenant-local times of day (HH:MM); stored as a sorted JSON array of "HH:MM:SS". */
  | 'timeList';

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
  /** Allowed values for `enum` and `multiEnum` fields. */
  options?: readonly FieldOption[];
  /** `multiEnum`: fewest values that must be chosen (default 1). */
  minItems?: number;
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

export const EXPENSE_CAPTURE_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'receipt_required_above',
    label: 'Receipt required above',
    kind: 'decimal',
    help: 'Expenses above this amount (tenant currency) need a receipt photo; 0 means every expense.',
  },
  { key: 'gps_required', label: 'GPS required on expenses', kind: 'bool' },
  { key: 'gps_max_accuracy_m', label: 'Maximum GPS accuracy', kind: 'number', unit: 'm' },
  {
    key: 'auto_approve_limit',
    label: 'Auto-approve up to',
    kind: 'decimal',
    help: 'Expenses up to this amount are approved automatically; 0 means every expense needs an approver.',
  },
];

export const POLICY_FIELDS: Readonly<Record<PolicyType, readonly PolicyFieldDef[]>> = {
  TRACKING: TRACKING_FIELDS,
  METER_CAPTURE: METER_CAPTURE_FIELDS,
  HIRE_BILLING: HIRE_BILLING_FIELDS,
  DEVICE_SYNC: DEVICE_SYNC_FIELDS,
  EXPENSE_CAPTURE: EXPENSE_CAPTURE_FIELDS,
  FRAUD_CONTROLS: FRAUD_CONTROLS_FIELDS,
  CASH_CUSTODY: CASH_CUSTODY_FIELDS,
  OVERSIGHT: OVERSIGHT_FIELDS,
  CUSTOMER_HOURS: CUSTOMER_HOURS_FIELDS,
  ENGINE_HOURS: ENGINE_HOURS_FIELDS,
  REVENUE_RECONCILIATION: REVENUE_RECONCILIATION_FIELDS,
};

export const POLICY_TYPE_LABELS: Readonly<Record<PolicyType, string>> = {
  TRACKING: 'Tracking',
  METER_CAPTURE: 'Meter capture',
  HIRE_BILLING: 'Hire billing',
  DEVICE_SYNC: 'Device sync',
  EXPENSE_CAPTURE: 'Expense capture',
  FRAUD_CONTROLS: 'Risk signals',
  CASH_CUSTODY: 'Cash custody',
  OVERSIGHT: 'Oversight',
  CUSTOMER_HOURS: 'Customer hours',
  ENGINE_HOURS: 'Engine hours',
  REVENUE_RECONCILIATION: 'Revenue checks',
};

export type OverrideScope = 'TENANT' | 'MACHINE_CATEGORY' | 'MACHINE' | 'SITE' | 'STAFF';

type LowerScope = Exclude<OverrideScope, 'TENANT'>;

/**
 * MACHINE and SITE are listed for every overridable type; STAFF and MACHINE_CATEGORY only where the
 * backend allows them.
 */
type LowerScopeFields = Readonly<
  Record<'MACHINE' | 'SITE', ReadonlySet<string>> & {
    STAFF?: ReadonlySet<string>;
    MACHINE_CATEGORY?: ReadonlySet<string>;
  }
>;

/** Fields a lower scope may override (mirrors the backend OVERRIDABLE table; tenant = all). */
const SCOPE_FIELDS: Readonly<Record<PolicyType, LowerScopeFields | null>> = {
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
  EXPENSE_CAPTURE: null,
  // Only the cash holding allowance varies by site or person (DEC-031 D3).
  CASH_CUSTODY: {
    MACHINE: new Set<string>(),
    SITE: new Set(['max_holding_days']),
    STAFF: new Set(['max_holding_days']),
  },
  OVERSIGHT: null,
  CUSTOMER_HOURS: null,
  REVENUE_RECONCILIATION: null,
  FRAUD_CONTROLS: {
    MACHINE: new Set([
      'engine_activity_min_minutes',
      'fuel_max_litres_per_meter_hour',
      'expense_threshold_per_machine_per_week',
      'engine_without_work_case_min_minutes',
      'fuel_litres_per_hour_max',
    ]),
    SITE: new Set<string>(),
    // The fuel norm per engine hour varies by machine category (DEC-031 S2).
    MACHINE_CATEGORY: new Set(['fuel_litres_per_hour_max']),
  },
  ENGINE_HOURS: {
    MACHINE: new Set(['baseline_required_before_start', 'daily_report_required']),
    SITE: new Set<string>(),
  },
};

/** Scopes at which a tenant may version this policy type. */
export function scopesFor(ptype: PolicyType): readonly OverrideScope[] {
  const lower = SCOPE_FIELDS[ptype];
  if (lower === null) return ['TENANT'];
  const scopes: LowerScope[] = ['MACHINE_CATEGORY', 'MACHINE', 'SITE', 'STAFF'];
  return ['TENANT', ...scopes.filter((scope) => (lower[scope]?.size ?? 0) > 0)];
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

/** A 24-hour time of day, HH:MM. */
export const TIME_OF_DAY = /^([01]\d|2[0-3]):[0-5]\d$/;

/** Human display of a policy value. */
export function formatPolicyValue(def: PolicyFieldDef | undefined, value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (def?.kind === 'weekdays' && Array.isArray(value)) {
    return value
      .map((d) => (typeof d === 'number' ? (WEEKDAYS[d] ?? String(d)) : String(d)))
      .join(', ');
  }
  if (def?.kind === 'bool' && typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (def?.kind === 'timeList' && Array.isArray(value)) {
    return value.length === 0 ? 'None' : value.map((t) => String(t).slice(0, 5)).join(', ');
  }
  if (def?.kind === 'multiEnum' && Array.isArray(value)) {
    if (value.length === 0) return 'None';
    return value.map((v) => def.options?.find((o) => o.value === v)?.label ?? String(v)).join(', ');
  }
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
  if (def.kind === 'multiEnum') return Array.isArray(value) ? value.map(String).join(',') : '';
  if (def.kind === 'timeList') {
    return Array.isArray(value) ? value.map((t) => String(t).slice(0, 5)).join(',') : '';
  }
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
      return v;
    case 'enum':
      return v === '' ? null : v; // an empty option ('Off') stores null
    case 'nullableDecimal':
      return v === '' ? null : v;
    case 'bool':
      return v === 'true';
    case 'multiEnum':
      return v === '' ? [] : splitMulti(def, v);
    case 'timeList':
      return splitTimes(v).map((t) => `${t}:00`);
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
    case 'nullableDecimal':
      return v === '' || /^\d+(\.\d+)?$/.test(v) ? null : 'Enter a decimal number or leave empty';
    case 'bool':
      return v === 'true' || v === 'false' ? null : 'Choose yes or no';
    case 'enum':
      return def.options?.some((o) => o.value === v) === true ? null : 'Choose a value';
    case 'timeList':
      return v.split(',').every((t) => t.trim() === '' || TIME_OF_DAY.test(t.trim()))
        ? null
        : 'Use HH:MM (24 h) for every time';
    case 'multiEnum': {
      const chosen = v === '' ? [] : v.split(',');
      const min = def.minItems ?? 1;
      if (chosen.some((c) => def.options?.some((o) => o.value === c) !== true)) {
        return 'Choose from the listed values';
      }
      return chosen.length >= min
        ? null
        : `Choose at least ${String(min)} value${min === 1 ? '' : 's'}`;
    }
  }
}

/** Time-list input ('12:00,06:30') → sorted, distinct HH:MM values (blanks dropped). */
export function splitTimes(input: string): string[] {
  const times = input
    .split(',')
    .map((t) => t.trim())
    .filter((t) => t !== '');
  return [...new Set(times)].sort();
}

/** Multi-select input ('A,B') → values in the order of `options` (stable, no duplicates). */
function splitMulti(def: PolicyFieldDef, input: string): string[] {
  const chosen = new Set(input.split(','));
  return (def.options ?? []).map((o) => o.value).filter((v) => chosen.has(v));
}
