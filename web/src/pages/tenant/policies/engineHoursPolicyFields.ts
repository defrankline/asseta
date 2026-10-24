/** Engine-hour accountability policy fields (ENGINE_HOURS; mirrors backend EngineHoursPolicy). */
import type { PolicyFieldDef } from './policyFields';

export const ENGINE_HOURS_FIELDS: readonly PolicyFieldDef[] = [
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
