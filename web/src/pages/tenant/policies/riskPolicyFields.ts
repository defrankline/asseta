/** Risk-signal thresholds (FRAUD_CONTROLS; labelled "Risk signals"). Empty nullable values switch a check off. */
import type { PolicyFieldDef } from './policyFields';

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
  {
    key: 'engine_without_work_case_min_minutes',
    label: 'Engine running without work (one case per machine and day)',
    kind: 'nullableNumber',
    unit: 'min',
    help:
      'Tracker engine-on time without a job, unexplained meter hours outside jobs and after-hours movement of ' +
      'one machine on one day are reviewed as one case; a day with at least this much adds a day summary. ' +
      'Empty = off.',
  },
  {
    key: 'fuel_check_period',
    label: 'Fuel against engine hours: check period',
    kind: 'enum',
    options: [
      { value: '', label: 'Off' },
      { value: 'DAY', label: 'Per day' },
      { value: 'WEEK', label: 'Per week' },
    ],
    help: 'All fuel issued or purchased into each machine compared with its engine hours, inside or outside jobs.',
  },
  {
    key: 'fuel_litres_per_hour_max',
    label: 'Fuel norm per engine hour',
    kind: 'nullableDecimal',
    unit: 'L per engine hour',
    help: 'Set for the company, a machine category or one machine (the most specific applies). Empty = off.',
  },
];
