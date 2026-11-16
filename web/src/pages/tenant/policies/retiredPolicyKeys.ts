/**
 * Settings the server retired (ADR-008: jobs, contracts, hire invoices, site check-ins, unbilled work;
 * backend `RETIRED_FIELDS`). The effective policy never returns them, but versions stored before they
 * were retired still carry them in their `values`; the version history leaves them out.
 */
export const RETIRED_POLICY_KEYS: ReadonlySet<string> = new Set([
  // CUSTOMER_HOURS
  'walk_in_standard_contract',
  'prepaid_job_auto_approval',
  'billing_modes',
  'default_billing_mode',
  'over_consumption',
  'overrun_exception_blocking',
  'drawdown',
  'reversal_used_hours_treatment',
  // ENGINE_HOURS
  'baseline_required_before_start',
  'prevent_overlapping_allocation',
  'prevent_overlapping_activity',
  'in_job_time_counts_as_customer_work',
  'changeover_splits_billing',
  // METER_CAPTURE
  'opening_mode',
  // FRAUD_CONTROLS
  'engine_activity_min_minutes',
  'authorization_tolerance_minutes',
  'engine_without_work_case_min_minutes',
  // OVERSIGHT
  'unbilled_after_days',
  'site_checkin_required',
  'site_checkin_times',
  'site_checkin_window_minutes',
  'site_checkin_max_distance_m',
]);

/** Settings stored under an older name, read under the new one (backend `RENAMED_FIELDS`). */
export const RENAMED_POLICY_KEYS: Readonly<Record<string, string>> = {
  closing_mode: 'capture_mode',
};
