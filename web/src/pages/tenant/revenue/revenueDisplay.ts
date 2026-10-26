/** Labels, tones and error hints for revenue checks (DEC-031). Neutral wording: a difference to explain. */
import type {
  NonRevenueActivityDto,
  RevenueDifferenceDto,
  RevenueDifferenceStatus,
  SheetFlag,
  SheetMoneySourceDto,
} from '../../../api/types';
import type { StatusTone } from '../../../components/display/StatusChip';
import type { Option } from '../shared/display';
import { machineText } from '../shared/names';
import { ACTIVITY_TYPE_OPTIONS } from '../shared/jobDisplay';

export const DIFFERENCE_STATUS_LABELS: Readonly<Record<RevenueDifferenceStatus, string>> = {
  OPEN: 'To explain',
  EXPLANATION_PROPOSED: 'Explanation awaiting decision',
  EXPLAINED: 'Explained',
  CONFIRMED: 'Confirmed (money to recover)',
  CLEARED: 'Cleared (money arrived)',
};

export const DIFFERENCE_STATUS_TONES: Readonly<Record<RevenueDifferenceStatus, StatusTone>> = {
  OPEN: 'warning',
  EXPLANATION_PROPOSED: 'info',
  EXPLAINED: 'success',
  CONFIRMED: 'error',
  CLEARED: 'default',
};

export const DIFFERENCE_STATUS_OPTIONS: readonly Option<RevenueDifferenceStatus>[] = [
  { value: 'OPEN', label: 'To explain' },
  { value: 'EXPLANATION_PROPOSED', label: 'Explanation awaiting decision' },
  { value: 'EXPLAINED', label: 'Explained' },
  { value: 'CONFIRMED', label: 'Confirmed (money to recover)' },
  { value: 'CLEARED', label: 'Cleared (money arrived)' },
];

export const PERIOD_KIND_LABELS: Readonly<Record<string, string>> = {
  DAY: 'Day',
  WEEK: 'Week',
  JOB: 'Job',
};

export const SHEET_FLAG_LABELS: Readonly<Record<SheetFlag, string>> = {
  MISSING_DAILY_REPORT: 'Daily report missing',
  UNEXPLAINED_HOURS: 'Hours to explain',
  ENGINE_ON_WITHOUT_JOB: 'Engine on without a job',
  FUEL_ABOVE_NORM: 'Fuel above the norm',
  REVENUE_DIFFERENCE: 'Revenue difference',
};

export const SHEET_FLAG_OPTIONS: readonly Option<SheetFlag>[] = (
  Object.keys(SHEET_FLAG_LABELS) as SheetFlag[]
).map((value) => ({ value, label: SHEET_FLAG_LABELS[value] }));

export const MONEY_SOURCE_LABELS: Readonly<Record<SheetMoneySourceDto['source'], string>> = {
  INVOICE_LINE: 'Invoice line',
  PREPAID_CONSUMPTION: 'Prepaid hours used',
};

export const ADJUSTMENT_CAUSE_LABELS: Readonly<Record<string, string>> = {
  engine_hour_classification: 'Engine hours explained',
  non_revenue_approval: 'Non-revenue time approved',
};

type ApprovalStatus = NonRevenueActivityDto['approval_status'];

/** Status of non-revenue time: until approved it counts as revenue. */
export const ACTIVITY_STATUS_LABELS: Readonly<Record<ApprovalStatus, string>> = {
  NONE: 'Counts as revenue (not explained)',
  PROPOSED: 'Explanation awaiting decision',
  APPROVED: 'Approved as non-revenue',
  REJECTED: 'Rejected (counts as revenue)',
};

export const ACTIVITY_STATUS_TONES: Readonly<Record<ApprovalStatus, StatusTone>> = {
  NONE: 'warning',
  PROPOSED: 'info',
  APPROVED: 'success',
  REJECTED: 'default',
};

export const ACTIVITY_STATUS_OPTIONS: readonly Option<ApprovalStatus>[] = [
  { value: 'NONE', label: 'Not explained' },
  { value: 'PROPOSED', label: 'Awaiting decision' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'REJECTED', label: 'Rejected' },
];

/** Approval record statuses (PROPOSED | APPROVED | REJECTED). */
export const APPROVAL_STATUS_LABELS: Readonly<Record<string, string>> = {
  PROPOSED: 'Awaiting decision',
  APPROVED: 'Approved as non-revenue',
  REJECTED: 'Rejected',
};

export const APPROVAL_STATUS_TONES: Readonly<Record<string, StatusTone>> = {
  PROPOSED: 'info',
  APPROVED: 'success',
  REJECTED: 'default',
};

export const APPROVAL_STATUS_OPTIONS: readonly Option[] = [
  { value: 'PROPOSED', label: 'Awaiting decision' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'REJECTED', label: 'Rejected' },
];

/** "Movement (mobilization)" etc.; unknown types humanised by the caller. */
export const activityTypeLabel = (type: string): string =>
  type === 'MOBILIZATION'
    ? 'Movement (mobilization)'
    : (ACTIVITY_TYPE_OPTIONS.find((o) => o.value === type)?.label ?? type);

/** "Movement 1.50 h · Standby 0.25 h" (hours per non-revenue type), or "—". */
export function hoursByTypeText(byType: Readonly<Record<string, string>>): string {
  const parts = Object.entries(byType)
    .filter(([, h]) => Number(h) !== 0)
    .map(([type, h]) => `${activityTypeLabel(type)} ${h} h`);
  return parts.length === 0 ? '—' : parts.join(' · ');
}

/** Disabled-decision tooltip on one's own request (the server enforces it too). */
export const OWN_REQUEST_TEXT = 'Someone else must decide your own request';

/** The server needs a note (5–2000 characters) on every explanation and decision. */
export const NOTE_MIN = 5;

/** Stable revenue error codes with what the user can do about them. */
export const REVENUE_ERROR_HINTS: Readonly<Record<string, string>> = {
  REVENUE_RECONCILIATION_DISABLED:
    'Revenue checks are switched off for your company (Policies → Revenue checks).',
  SEGREGATION_OF_DUTIES: 'You explained this, so someone else must decide it.',
  REVENUE_DIFFERENCE_NOT_OPEN:
    'This difference is no longer open to explain; reload to see its status.',
  REVENUE_DIFFERENCE_STATE: 'This difference cannot take that decision now; reload.',
  REASON_INACTIVE: 'This reason was deactivated; choose an active one.',
  REVENUE_REASON_NOT_FOUND: 'This reason no longer exists; choose another.',
  DUPLICATE_REASON: 'A reason with this code already exists.',
  NON_REVENUE_PENDING: 'An explanation of this time already awaits a decision.',
  NON_REVENUE_APPROVAL_NOT_REQUIRED:
    'Your policy does not need approval for non-revenue time, so nothing to explain.',
  NOT_NON_REVENUE_ACTIVITY:
    'This work-log entry is not non-revenue time under your policy (billable, open or another type).',
  ACTIVITY_NOT_FOUND: 'This work-log entry no longer exists; reload.',
  ALREADY_DECIDED: 'This request has already been decided; reload to see the outcome.',
  RANGE_TOO_LONG: 'Choose at most 93 days.',
  INVALID_RANGE: 'The “from” day must not be after the “to” day.',
  STALE_VERSION: 'Someone else changed this record; reload and try again.',
};

/** "Day 2026-10-20", "Week 2026-10-19 → 2026-10-25" or "Job J-100". */
export const differencePeriod = (d: RevenueDifferenceDto): string => {
  const kind = PERIOD_KIND_LABELS[d.period_kind] ?? d.period_kind;
  if (d.period_kind === 'JOB') return `${kind} ${d.job_number ?? d.period_key}`;
  return d.local_from === d.local_to
    ? `${kind} ${d.local_from}`
    : `${kind} ${d.local_from} → ${d.local_to}`;
};

/** Machine code · name of a record carrying machine fields. */
export const differenceMachine = (d: {
  machine_id: string;
  machine_code?: string | null;
  machine_name?: string | null;
}): string => machineText(d.machine_code, d.machine_name, d.machine_id);
