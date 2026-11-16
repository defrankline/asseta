/**
 * Keys the server no longer uses (ADR-008: jobs, booking with a sale, site check-ins, unbilled work).
 * Older stored versions may still carry them; they are not shown.
 */
export const RETIRED_POLICY_KEYS: ReadonlySet<string> = new Set([
  'walk_in_standard_contract',
  'prepaid_job_auto_approval',
  'billing_modes',
  'default_billing_mode',
  'over_consumption',
  'overrun_exception_blocking',
  'drawdown',
  'unbilled_after_days',
  'site_checkin_required',
  'site_checkin_times',
  'site_checkin_window_minutes',
  'site_checkin_max_distance_m',
  'in_job_time_counts_as_customer_work',
  'changeover_splits_billing',
  'prevent_overlapping_allocation',
  'authorization_tolerance_minutes',
]);
