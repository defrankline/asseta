/** Labels, tones and error hints for engine-hour accountability screens (neutral wording throughout). */
import type {
  ClassificationOutcome,
  IntervalDto,
  SegmentDto,
  EngineHourReasonKind,
  MeterProposalStatus,
  ReadingReview,
  ReconciliationStatus,
  SegmentClassification,
} from '../../../api/types';
import type { StatusTone } from '../../../components/display/StatusChip';
import type { Option } from '../shared/display';

export const PROPOSAL_STATUS_TONES: Readonly<Record<MeterProposalStatus, StatusTone>> = {
  PROPOSED: 'info',
  APPROVED: 'success',
  REJECTED: 'default',
};

export const PROPOSAL_STATUS_LABELS: Readonly<Record<MeterProposalStatus, string>> = {
  PROPOSED: 'Awaiting decision',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
};

export const PROPOSAL_STATUS_OPTIONS: readonly Option<MeterProposalStatus>[] = [
  { value: 'PROPOSED', label: 'Awaiting decision' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'REJECTED', label: 'Rejected' },
];

export const RECONCILIATION_TONES: Readonly<Record<ReconciliationStatus, StatusTone>> = {
  NO_BASELINE: 'default',
  RECONCILED: 'success',
  PENDING_REVIEW: 'info',
  UNEXPLAINED: 'warning',
};

export const RECONCILIATION_LABELS: Readonly<Record<ReconciliationStatus, string>> = {
  NO_BASELINE: 'No approved baseline',
  RECONCILED: 'All hours explained',
  PENDING_REVIEW: 'Readings under review',
  UNEXPLAINED: 'Hours to explain',
};

export const RECONCILIATION_OPTIONS: readonly Option<ReconciliationStatus>[] = [
  { value: 'UNEXPLAINED', label: 'Hours to explain' },
  { value: 'PENDING_REVIEW', label: 'Readings under review' },
  { value: 'NO_BASELINE', label: 'No approved baseline' },
  { value: 'RECONCILED', label: 'All hours explained' },
];

export const CLASSIFICATION_LABELS: Readonly<Record<SegmentClassification, string>> = {
  NOT_APPLICABLE: 'Customer work',
  UNEXPLAINED: 'Not yet explained',
  APPROVED_NON_CUSTOMER: 'Non-customer activity',
  IDENTIFIED_VARIANCE: 'Identified variance',
};

export const CLASSIFICATION_TONES: Readonly<Record<SegmentClassification, StatusTone>> = {
  NOT_APPLICABLE: 'success',
  UNEXPLAINED: 'warning',
  APPROVED_NON_CUSTOMER: 'info',
  IDENTIFIED_VARIANCE: 'default',
};

/** Unallocated list filter (default = open items: verified and not yet explained). */
export const SEGMENT_FILTER_OPTIONS: readonly Option<SegmentClassification>[] = [
  { value: 'UNEXPLAINED', label: 'Not yet explained (all)' },
  { value: 'APPROVED_NON_CUSTOMER', label: 'Non-customer activity' },
  { value: 'IDENTIFIED_VARIANCE', label: 'Identified variance' },
];

export const OUTCOME_LABELS: Readonly<Record<ClassificationOutcome, string>> = {
  APPROVED_NON_CUSTOMER: 'Non-customer activity',
  IDENTIFIED_VARIANCE: 'Identified variance',
};

export const OUTCOME_OPTIONS: readonly Option<ClassificationOutcome>[] = [
  { value: 'APPROVED_NON_CUSTOMER', label: 'Non-customer activity (maintenance, relocation, …)' },
  { value: 'IDENTIFIED_VARIANCE', label: 'Identified variance (with a reason)' },
];

/** The tenant list kind a classification outcome draws its reason from. */
export const OUTCOME_REASON_KIND: Readonly<Record<ClassificationOutcome, EngineHourReasonKind>> = {
  APPROVED_NON_CUSTOMER: 'NON_CUSTOMER_CATEGORY',
  IDENTIFIED_VARIANCE: 'VARIANCE_REASON',
};

export const REASON_KIND_LABELS: Readonly<Record<EngineHourReasonKind, string>> = {
  NON_CUSTOMER_CATEGORY: 'Non-customer activity category',
  VARIANCE_REASON: 'Variance reason',
};

export const REASON_KIND_OPTIONS: readonly Option<EngineHourReasonKind>[] = [
  { value: 'NON_CUSTOMER_CATEGORY', label: 'Non-customer activity category' },
  { value: 'VARIANCE_REASON', label: 'Variance reason' },
];

export const REVIEW_LABELS: Readonly<Record<ReadingReview, string>> = {
  VERIFIED: 'Verified readings',
  PENDING_REVIEW: 'Reading under review',
};

export const READING_SOURCE_LABELS: Readonly<Record<string, string>> = {
  BASELINE: 'Baseline',
  OPENING: 'Opening',
  CLOSING: 'Closing',
  DAILY: 'Daily',
};

export const sourceLabel = (source: string): string => READING_SOURCE_LABELS[source] ?? source;

/** Disabled-decision tooltip on one's own proposal (the server enforces it too). */
export const OWN_PROPOSAL_TEXT = 'Someone else must decide your own request';

/** Hours as returned (decimal string), with a unit. */
export const hoursText = (hours: string | null | undefined): string =>
  hours === null || hours === undefined ? '—' : `${hours} h`;

export const isPositive = (hours: string): boolean => Number(hours) > 0;

/** Stable engine-hour error codes with what the user can do about them. */
export const ENGINE_HOURS_ERROR_HINTS: Readonly<Record<string, string>> = {
  SEGREGATION_OF_DUTIES: 'You proposed this, so someone else must decide it.',
  BASELINE_REQUIRED: 'Approve a meter baseline for this machine first.',
  BASELINE_PENDING: 'A baseline proposal for this machine already awaits a decision.',
  BASELINE_EXISTS: 'This machine already has an approved baseline; use a meter reset to re-base.',
  SEGMENT_NOT_UNEXPLAINED:
    'Only verified, not-yet-explained hours can be classified; reload to see the current ledger.',
  SEGMENT_NOT_FOUND:
    'These hours changed since the page loaded (a reading was added or corrected); reload.',
  CLASSIFICATION_PENDING: 'An explanation of these hours already awaits a decision.',
  REASON_NOT_ALLOWED: 'Choose an active entry of the matching list.',
  ALREADY_DECIDED: 'This request has already been decided; reload to see the outcome.',
  SEGMENT_CHANGED:
    'These hours changed since the explanation was proposed (a correction or late reading); propose again.',
  CAPTURE_NOT_ACTIVE: 'Only a live reading (accepted or provisional) can be corrected.',
  CORRECTION_MISMATCH: 'The corrected reading must be the same kind of reading for the same job.',
  BASELINE_INCONSISTENT:
    'The baseline is above a later reading of this machine; check the value or record a meter reset.',
  BASELINE_IN_FUTURE: 'A baseline cannot be taken in the future.',
  DUPLICATE_REASON: 'An entry with this code already exists.',
  CORRECTION_PENDING: 'A correction of this reading already awaits a decision.',
  CAPTURE_ID_CONFLICT:
    'This reading was already recorded with different values; close the dialog and start again.',
  STALE_VERSION: 'Someone else changed this record; reload and try again.',
};

/** An unallocated segment that can be explained now (verified, unexplained, nothing proposed). */
export function isOpenItem(interval: IntervalDto, segment: SegmentDto): boolean {
  return (
    interval.review === 'VERIFIED' &&
    segment.kind === 'UNALLOCATED' &&
    segment.classification === 'UNEXPLAINED' &&
    segment.proposal === null &&
    isPositive(segment.hours)
  );
}
