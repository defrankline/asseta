/**
 * Policy field catalogues (labels/units/kinds) per policy type and which fields each override scope may
 * set (mirrors the backend OVERRIDABLE table; tenant = all fields).
 */
import type { PolicyType } from '../../../api/types';
import { CASH_CUSTODY_FIELDS, OVERSIGHT_FIELDS } from './accountabilityPolicyFields';
import { ENGINE_HOURS_FIELDS } from './engineHoursPolicyFields';

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
  | 'enum';

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

export const FRAUD_CONTROLS_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'engine_activity_min_minutes',
    label: 'Engine activity without a running job',
    kind: 'int',
    unit: 'min',
    help: 'Verified ignition / engine-hour activity at least this long with no job in progress needs review.',
  },
  {
    key: 'fuel_max_litres_per_meter_hour',
    label: 'Fuel allowance',
    kind: 'nullableDecimal',
    unit: 'L per meter hour',
    help: 'Leave empty to switch the fuel allowance check off.',
  },
  {
    key: 'expense_threshold_per_machine_per_week',
    label: 'Weekly spending per machine',
    kind: 'nullableDecimal',
    help: 'Approved + pending expenses (tenant currency) above this per ISO week need review; empty = off.',
  },
  { key: 'cash_outstanding_max_hours', label: 'Cash held at most', kind: 'int', unit: 'h' },
  {
    key: 'cash_outstanding_max_amount',
    label: 'Cash held up to',
    kind: 'nullableDecimal',
    help: 'Outstanding supervisor custody above this amount needs review; empty = off.',
  },
  {
    key: 'case_grouping_window_hours',
    label: 'Case grouping window',
    kind: 'int',
    unit: 'h',
    help: 'New signals on the same subject join its open case within this window.',
  },
  {
    key: 'duplicate_receipt_lookback_days',
    label: 'Duplicate receipt lookback',
    kind: 'int',
    unit: 'days',
  },
  {
    key: 'authorization_tolerance_minutes',
    label: 'Job authorization clock tolerance',
    kind: 'int',
    unit: 'min',
  },
  {
    key: 'detection_lookback_hours',
    label: 'Detection lookback',
    kind: 'int',
    unit: 'h',
    help: 'How far back each periodic check re-examines records.',
  },
];

export const CUSTOMER_HOURS_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'enabled',
    label: 'Customer hours switched on',
    kind: 'bool',
    help: 'Off: no purchases or prepaid jobs; jobs are invoiced.',
  },
  { key: 'walk_in_allowed', label: 'Walk-in customers allowed', kind: 'bool' },
  {
    key: 'default_billing_mode',
    label: 'Default billing of new jobs',
    kind: 'enum',
    options: [
      { value: 'INVOICE', label: 'Invoice after the work' },
      { value: 'PREPAID_HOURS', label: 'Prepaid customer hours' },
    ],
  },
  { key: 'partial_activation', label: 'Partial payments activate hours pro rata', kind: 'bool' },
  {
    key: 'hours_increment',
    label: 'Activation step',
    kind: 'decimal',
    unit: 'h',
    help: 'Activated hours are rounded down to this step.',
  },
  {
    key: 'expiry_days',
    label: 'Unused hours expire after',
    kind: 'nullableNumber',
    unit: 'days',
    help: 'Counted from activation; leave empty to never expire.',
  },
  { key: 'expiry_warning_days', label: 'Warn before expiry', kind: 'int', unit: 'days' },
  {
    key: 'over_consumption',
    label: 'When a prepaid job has no hours left',
    kind: 'enum',
    options: [
      { value: 'BLOCK_START', label: 'Do not let the job start' },
      { value: 'FLAG_EXCESS', label: 'Allow it and flag the excess' },
    ],
  },
  {
    key: 'overrun_exception_blocking',
    label: 'Excess hours block the job until reviewed',
    kind: 'bool',
  },
  {
    key: 'transfer_requires_approval',
    label: 'Transfers between machines need a second person',
    kind: 'bool',
  },
  {
    key: 'cancellation_requires_approval',
    label: 'Cancellations need a second person',
    kind: 'bool',
  },
  {
    key: 'cancellation_after_consumption_allowed',
    label: 'Cancel the rest of a partly used purchase',
    kind: 'bool',
  },
  { key: 'discount_requires_approval', label: 'Discounts need a second person', kind: 'bool' },
  { key: 'max_discount_percent', label: 'Highest discount', kind: 'decimal', unit: '%' },
  { key: 'credit_allowed', label: 'Credit arrangements allowed', kind: 'bool' },
  { key: 'reason_code_required', label: 'A reason from the tenant list is required', kind: 'bool' },
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
  EXPENSE_CAPTURE: null,
  CASH_CUSTODY: null,
  OVERSIGHT: null,
  CUSTOMER_HOURS: null,
  FRAUD_CONTROLS: {
    MACHINE: new Set([
      'engine_activity_min_minutes',
      'fuel_max_litres_per_meter_hour',
      'expense_threshold_per_machine_per_week',
    ]),
    SITE: new Set<string>(),
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
  const scopes: LowerScope[] = ['MACHINE', 'SITE'];
  return ['TENANT', ...scopes.filter((scope) => lower[scope].size > 0)];
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
    case 'nullableDecimal':
      return v === '' ? null : v;
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
    case 'nullableDecimal':
      return v === '' || /^\d+(\.\d+)?$/.test(v) ? null : 'Enter a decimal number or leave empty';
    case 'bool':
      return v === 'true' || v === 'false' ? null : 'Choose yes or no';
    case 'enum':
      return def.options?.some((o) => o.value === v) === true ? null : 'Choose a value';
  }
}
