/** Labels, tones and helpers of the work allocation ledger and daily reports (DEC-032 Phase 1). */
import type {
  AllocationKind,
  AllocationStatus,
  DailyReportStatus,
  ReportAllocationDto,
  WorkAllocationDto,
} from '../../../../api/allocationTypes';
import type { StatusTone } from '../../../../components/display/StatusChip';
import { humanize } from '../../../../utils/text';
import type { Option } from '../../shared/display';
import { activityTypeLabel } from '../../shared/jobDisplay';

export const KIND_LABELS: Readonly<Record<AllocationKind, string>> = {
  CUSTOMER_WORK: 'Customer work',
  AUTHORIZED_ACTIVITY: 'Authorized activity',
  UNEXPLAINED: 'Unexplained',
};

export const KIND_TONES: Readonly<Record<AllocationKind, StatusTone>> = {
  CUSTOMER_WORK: 'success',
  AUTHORIZED_ACTIVITY: 'info',
  UNEXPLAINED: 'warning',
};

export const KIND_OPTIONS: readonly Option<AllocationKind>[] = [
  { value: 'CUSTOMER_WORK', label: KIND_LABELS.CUSTOMER_WORK },
  { value: 'AUTHORIZED_ACTIVITY', label: KIND_LABELS.AUTHORIZED_ACTIVITY },
  { value: 'UNEXPLAINED', label: KIND_LABELS.UNEXPLAINED },
];

export const STATUS_LABELS: Readonly<Record<AllocationStatus, string>> = {
  PROPOSED: 'Awaiting decision',
  ACTIVE: 'Active',
  SUPERSEDED: 'Superseded',
  REJECTED: 'Rejected',
};

export const STATUS_TONES: Readonly<Record<AllocationStatus, StatusTone>> = {
  PROPOSED: 'info',
  ACTIVE: 'success',
  SUPERSEDED: 'default',
  REJECTED: 'default',
};

export const STATUS_OPTIONS: readonly Option<AllocationStatus>[] = [
  { value: 'ACTIVE', label: STATUS_LABELS.ACTIVE },
  { value: 'PROPOSED', label: STATUS_LABELS.PROPOSED },
  { value: 'SUPERSEDED', label: STATUS_LABELS.SUPERSEDED },
  { value: 'REJECTED', label: STATUS_LABELS.REJECTED },
];

export const REPORT_STATUS_LABELS: Readonly<Record<DailyReportStatus, string>> = {
  SUBMITTED: 'To review',
  REVIEWED: 'Reviewed',
  RETURNED: 'Returned',
  SUPERSEDED: 'Replaced',
};

export const REPORT_STATUS_TONES: Readonly<Record<DailyReportStatus, StatusTone>> = {
  SUBMITTED: 'info',
  REVIEWED: 'success',
  RETURNED: 'warning',
  SUPERSEDED: 'default',
};

export const REPORT_STATUS_OPTIONS: readonly Option<DailyReportStatus>[] = [
  { value: 'SUBMITTED', label: REPORT_STATUS_LABELS.SUBMITTED },
  { value: 'REVIEWED', label: REPORT_STATUS_LABELS.REVIEWED },
  { value: 'RETURNED', label: REPORT_STATUS_LABELS.RETURNED },
  { value: 'SUPERSEDED', label: REPORT_STATUS_LABELS.SUPERSEDED },
];

/** Hours entered in forms (the server keeps two decimals). */
export const HOURS_PATTERN = /^\d+(\.\d{1,2})?$/;

/** Exact sums of two-decimal hours, in hundredths. */
export const toHundredths = (hours: string): number => Math.round(Number(hours) * 100);
export const fromHundredths = (units: number): string => (units / 100).toFixed(2);

export const isNonZero = (hours: string): boolean => Number(hours) !== 0;

type WhatFor = Pick<
  WorkAllocationDto | ReportAllocationDto,
  'kind' | 'customer_name' | 'job_number' | 'activity_type'
> & { reason_name?: string | null };

/** What the hours were for: customer and job, the activity, or nothing yet. */
export function allocationTarget(a: WhatFor): string {
  if (a.kind === 'CUSTOMER_WORK') {
    const job = a.job_number == null ? '' : ` · ${a.job_number}`;
    return `${a.customer_name ?? 'Customer'}${job}`;
  }
  if (a.kind === 'AUTHORIZED_ACTIVITY') {
    const activity = a.activity_type === null ? null : activityTypeLabel(a.activity_type);
    return (
      [activity, a.reason_name].filter((s): s is string => s != null).join(' · ') || 'Authorized'
    );
  }
  return 'Not explained';
}

export const sourceText = (source: string): string => humanize(source);
