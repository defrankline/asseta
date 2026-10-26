/** Policy field catalogues for the accountability controls (cash custody chain, oversight dashboard). */
import type { FieldOption, PolicyFieldDef } from './policyFields';

export const CASH_CUSTODY_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'enabled',
    label: 'Cash custody controls switched on',
    kind: 'bool',
    help: 'Off: transfers, acknowledgements, variances, retentions, adjustments, cash reasons and the remittance cut-off are hidden; collections, floats, remittances and reconciliation stay.',
  },
  {
    key: 'recorders_may_record_for_others',
    label: 'Recorders record for any custodian',
    kind: 'bool',
    help: 'Field recorders may record cash for staff without a login (otherwise own custody only).',
  },
  { key: 'transfer_ack_required', label: 'Receiver acknowledges transfers', kind: 'bool' },
  {
    key: 'recorder_receiver_counts_as_ack',
    label: 'Recording a transfer you receive acknowledges it',
    kind: 'bool',
  },
  { key: 'float_ack_required', label: 'Receiver acknowledges floats', kind: 'bool' },
  {
    key: 'remit_full_balance',
    label: 'Remit the full balance',
    kind: 'bool',
    help: 'A remittance leaving unretained cash with the custodian is flagged.',
  },
  {
    key: 'remittance_cutoff_hour',
    label: 'Daily remittance cut-off',
    kind: 'nullableNumber',
    unit: 'h',
    help: 'Tenant-local hour; leave empty for no daily cut-off.',
  },
  {
    key: 'variance_case_threshold',
    label: 'Open a case for differences above',
    kind: 'nullableDecimal',
    help: 'Leave empty to never open a case automatically.',
  },
  { key: 'writeoff_requires_approval', label: 'Write-offs need a second approver', kind: 'bool' },
  { key: 'retention_allowed', label: 'Approved retentions allowed', kind: 'bool' },
  {
    key: 'remittance_reference_required',
    label: 'Require a transaction reference for bank / mobile-money remittances',
    kind: 'bool',
    help: 'Cash handed to the office never needs one.',
  },
  {
    key: 'remittance_evidence_required',
    label: 'Require a photo of the deposit slip or payment confirmation',
    kind: 'bool',
  },
  {
    key: 'remittance_account_required',
    label: 'Require the company account the money was paid into',
    kind: 'bool',
  },
  {
    key: 'max_holding_days',
    label: 'Days a custodian may hold unremitted cash',
    kind: 'nullableNumber',
    unit: 'days',
    help: 'Leave empty for no limit. Cash covered by an approved retention does not count. Site and staff overrides allowed.',
  },
];

/** Accountability dashboard tiles (backend `accountability.service.TILES`). */
const DASHBOARD_TILES: readonly FieldOption[] = [
  { value: 'customer_hours', label: 'Customer hours' },
  { value: 'hours_awaiting_activation', label: 'Hours awaiting activation' },
  { value: 'engine_hours', label: 'Engine hours' },
  { value: 'unexplained_hours', label: 'Unexplained engine hours' },
  { value: 'missing_daily_reports', label: 'Missing daily reports' },
  { value: 'revenue_differences', label: 'Revenue differences' },
  { value: 'unbilled_work', label: 'Unbilled work' },
  { value: 'idle_machines', label: 'Idle machines' },
  { value: 'investigations', label: 'Investigations' },
  { value: 'cash', label: 'Cash' },
  { value: 'payments', label: 'Payments' },
  { value: 'discrepancies', label: 'Discrepancies' },
  { value: 'unauthorized_attempts', label: 'Refused attempts' },
  { value: 'outstanding_approvals', label: 'Outstanding approvals' },
];

const SCORECARD_ITEMS: readonly FieldOption[] = [
  { value: 'MISSING_DAILY_REPORT', label: 'Missing daily reports' },
  { value: 'LATE_DAILY_REPORT', label: 'Late daily reports' },
  { value: 'UNEXPLAINED_HOURS', label: 'Unexplained engine hours' },
  { value: 'ALERT', label: 'Tracking alerts' },
  { value: 'CASH_HELD_TOO_LONG', label: 'Cash held too long' },
  { value: 'CASH_DIFFERENCE', label: 'Cash differences' },
  { value: 'REVENUE_DIFFERENCE', label: 'Revenue differences' },
  { value: 'REFUSED_ATTEMPT', label: 'Refused attempts' },
  { value: 'MISSED_CHECKIN', label: 'Missed site check-ins' },
];

/** Check-in times every half hour; values as the API returns times (HH:MM:SS, tenant-local). */
const CHECKIN_TIMES: readonly FieldOption[] = Array.from({ length: 48 }, (_, i) => {
  const hhmm = `${String(Math.floor(i / 2)).padStart(2, '0')}:${i % 2 ? '30' : '00'}`;
  return { value: `${hhmm}:00`, label: hhmm };
});

/** DEC-031 Phase 5 (all off by default): people scorecard, unbilled work, idle machines, site check-ins. */
const PHASE5_OVERSIGHT_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'scorecard_enabled',
    label: 'People scorecard',
    kind: 'bool',
    help: 'Per-person figures (daily reports, unexplained hours, alerts, cash, differences, refused attempts) under Overview.',
  },
  {
    key: 'near_threshold_percent',
    label: 'Cash difference counted as just under the case threshold from',
    kind: 'nullableDecimal',
    unit: '%',
    help: 'Share of the cash case threshold; leave empty not to count them.',
  },
  {
    key: 'repeat_pattern_count',
    label: 'Repeated items that open a case',
    kind: 'nullableNumber',
    help: 'This many items of one kind for one person within the window raise a signal for review. Empty = off.',
  },
  { key: 'repeat_pattern_window_days', label: 'Repeated items window', kind: 'int', unit: 'days' },
  {
    key: 'repeat_pattern_items',
    label: 'Kinds of item counted for repeats',
    kind: 'multiEnum',
    options: SCORECARD_ITEMS,
    minItems: 0,
  },
  {
    key: 'unbilled_after_days',
    label: 'Completed work not invoiced after',
    kind: 'nullableNumber',
    unit: 'days',
    help: 'Billing-ready jobs not on an issued invoice after this many days are listed and notified. Empty = off.',
  },
  {
    key: 'idle_after_days',
    label: 'Machine idle after',
    kind: 'nullableNumber',
    unit: 'days',
    help: 'Active machines with no job and no engine hours for this many days are listed. Empty = off.',
  },
  {
    key: 'site_checkin_required',
    label: 'Supervisors check in at the site',
    kind: 'bool',
    help: 'GPS check-in in the Supervisor app at the times below while running a job. Shown to the person.',
  },
  {
    key: 'site_checkin_times',
    label: 'Check-in times',
    kind: 'multiEnum',
    options: CHECKIN_TIMES,
    minItems: 0,
  },
  {
    key: 'site_checkin_window_minutes',
    label: 'Check-in window (before or after)',
    kind: 'int',
    unit: 'min',
  },
  {
    key: 'site_checkin_max_distance_m',
    label: 'Check-in distance from the site',
    kind: 'nullableNumber',
    unit: 'm',
    help: 'Check-ins farther than this from the site centre are marked; leave empty to only show the distance.',
  },
];

export const OVERSIGHT_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'hidden_dashboard_tiles',
    label: 'Hidden dashboard tiles',
    kind: 'multiEnum',
    options: DASHBOARD_TILES,
    minItems: 0,
    help: 'Ticked tiles are hidden from the accountability dashboard.',
  },
  {
    key: 'security_event_window_days',
    label: 'Refused-attempts window',
    kind: 'int',
    unit: 'days',
  },
  ...PHASE5_OVERSIGHT_FIELDS,
];
