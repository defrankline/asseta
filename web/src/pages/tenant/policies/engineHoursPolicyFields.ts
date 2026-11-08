/** Engine-hour accountability policy fields (ENGINE_HOURS; mirrors backend EngineHoursPolicy). */
import type { PolicyFieldDef } from './policyFields';

export const ENGINE_HOURS_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'enabled',
    label: 'Engine-hour controls switched on',
    kind: 'bool',
    help: 'Off: engine-hour pages, baselines, corrections, daily readings and flags are hidden; job meter readings work as before.',
  },
  {
    key: 'baseline_required_before_start',
    label: 'Approved meter baseline before a job starts',
    kind: 'bool',
    help: 'Off: jobs start without an approved baseline (reconciliation still begins at the baseline).',
  },
  {
    key: 'daily_report_required',
    label: 'Daily report required',
    kind: 'bool',
    help: 'A working machine needs a meter reading every day by the cut-off hour.',
  },
  {
    key: 'daily_report_cutoff_hour',
    label: 'Daily report cut-off',
    kind: 'int',
    unit: 'h (local)',
  },
  {
    key: 'unexplained_investigation_after_days',
    label: 'Open an investigation for unexplained hours after',
    kind: 'nullableNumber',
    unit: 'days',
    help: 'Leave empty to never open a case. Time never changes how the hours are classified.',
  },
  {
    key: 'unexplained_flag_min_hours',
    label: 'Flag unexplained hours above',
    kind: 'decimal',
    unit: 'h',
  },
  {
    key: 'unexplained_flag_amount_hours',
    label: 'Open an investigation above this many unexplained hours per machine',
    kind: 'nullableDecimal',
    unit: 'h',
    help: 'Leave empty to look at age only. Cumulative per machine, once per multiple of the amount.',
  },
  {
    key: 'classification_requires_approval',
    label: 'Classifications need a second person',
    kind: 'bool',
    help: 'Off: a holder of the classify permission records the explanation directly.',
  },
  {
    key: 'correction_requires_second_person',
    label: 'Reading corrections need a second person',
    kind: 'bool',
  },
  {
    key: 'allocation_correction_requires_approval',
    label: 'Allocation corrections need a second person',
    kind: 'bool',
    help: 'Off: a reviewer corrects a work allocation directly; the original stays on record either way.',
  },
  {
    key: 'in_job_time_counts_as_customer_work',
    label: 'Time inside a job counts as customer work',
    kind: 'bool',
    help: 'Off: hours inside a job need a covering work-log entry; hours without one are unexplained.',
  },
  {
    key: 'changeover_splits_billing',
    label: "Hours after a changeover leave the job's billing",
    kind: 'bool',
    help: "On: the changeover must name the next customer's job; the hours after it leave this job's billing.",
  },
  {
    key: 'classification_evidence_required',
    label: 'Classifications need evidence',
    kind: 'bool',
  },
  {
    key: 'daily_report_evidence_required',
    label: 'Daily reports need a photo',
    kind: 'bool',
  },
  {
    key: 'ledger_includes_unreviewed_readings',
    label: 'Count readings still under review',
    kind: 'bool',
  },
  {
    key: 'prevent_overlapping_allocation',
    label: 'Refuse overlapping job intervals',
    kind: 'bool',
  },
  {
    key: 'prevent_overlapping_activity',
    label: 'Refuse overlapping work-log entries',
    kind: 'bool',
  },
];
