/** Runtime (Yup) response schemas for engine hours: baselines, the machine ledger, classifications, corrections. */
import { array, object, type Schema } from 'yup';
import type {
  BaselineDto,
  BaselineSource,
  ClassificationDto,
  ClassificationOutcome,
  ClassificationRefDto,
  CorrectionDto,
  EngineHourReasonDto,
  EngineHourReasonKind,
  EngineHourTotalsDto,
  IntervalDto,
  JobOverlapDto,
  LedgerPointDto,
  MachineEngineHoursDto,
  MachineEngineHoursSummaryDto,
  MeterProposalStatus,
  ReadingReview,
  ReconciliationStatus,
  SegmentClassification,
  SegmentDto,
  SegmentKind,
  UnallocatedSegmentDto,
} from '../types';
import {
  bool,
  id,
  idList,
  int,
  lifecycleFields,
  nullableId,
  nullableInt,
  nullableNum,
  nullableText,
  oneOf,
  text,
} from './schemaKit';

export const PROPOSAL_STATUSES: readonly MeterProposalStatus[] = [
  'PROPOSED',
  'APPROVED',
  'REJECTED',
];
export const BASELINE_SOURCES: readonly BaselineSource[] = ['CAPTURE', 'READING'];
export const REASON_KINDS: readonly EngineHourReasonKind[] = [
  'NON_CUSTOMER_CATEGORY',
  'VARIANCE_REASON',
];
export const RECONCILIATION_STATUSES: readonly ReconciliationStatus[] = [
  'NO_BASELINE',
  'RECONCILED',
  'PENDING_REVIEW',
  'UNEXPLAINED',
];
export const READING_REVIEWS: readonly ReadingReview[] = ['VERIFIED', 'PENDING_REVIEW'];
export const SEGMENT_KINDS: readonly SegmentKind[] = [
  'CUSTOMER_WORK',
  'UNALLOCATED',
  'NON_REVENUE',
];
export const SEGMENT_CLASSIFICATIONS: readonly SegmentClassification[] = [
  'NOT_APPLICABLE',
  'UNEXPLAINED',
  'APPROVED_NON_CUSTOMER',
  'IDENTIFIED_VARIANCE',
];
export const CLASSIFICATION_OUTCOMES: readonly ClassificationOutcome[] = [
  'APPROVED_NON_CUSTOMER',
  'IDENTIFIED_VARIANCE',
];

const optionalText = () => nullableText().optional();

const baselineFields = {
  id: id(),
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  reading: text(),
  captured_at: text(),
  source: oneOf(BASELINE_SOURCES),
  source_capture_id: nullableId(),
  photo_attachment_id: nullableId(),
  latitude: nullableNum(),
  longitude: nullableNum(),
  accuracy_m: nullableNum(),
  note: nullableText(),
  status: oneOf(PROPOSAL_STATUSES),
  proposed_by: nullableId(),
  proposed_by_name: optionalText(),
  proposed_at: text(),
  decided_by: nullableId(),
  decided_by_name: optionalText(),
  decided_at: nullableText(),
  decision_note: nullableText(),
};
export const baselineSchema: Schema<BaselineDto> = object(baselineFields);

export const engineHourReasonSchema: Schema<EngineHourReasonDto> = object({
  id: id(),
  kind: oneOf(REASON_KINDS),
  code: text(),
  name: text(),
  description: nullableText(),
  is_active: bool(),
  ...lifecycleFields(),
  deactivated_at: optionalText(),
  deactivation_reason: optionalText(),
});

const refFields = {
  id: id(),
  outcome: oneOf(CLASSIFICATION_OUTCOMES),
  reason_id: id(),
  status: oneOf(PROPOSAL_STATUSES),
};
export const classificationRefSchema: Schema<ClassificationRefDto> = object(refFields);

const nullableRef = () => object(refFields).nullable().defined();

const pointFields = {
  ref: id(),
  at: text(),
  reading: text(),
  source: text(),
  job_id: nullableId(),
};
export const ledgerPointSchema: Schema<LedgerPointDto> = object(pointFields);

const segmentSchema: Schema<SegmentDto> = object({
  kind: oneOf(SEGMENT_KINDS),
  hours: text(),
  classification: oneOf(SEGMENT_CLASSIFICATIONS),
  job_id: nullableId(),
  job_number: nullableText(),
  activity_type: optionalText(),
  approved: nullableRef(),
  proposal: nullableRef(),
});

const intervalSchema: Schema<IntervalDto> = object({
  machine_id: id(),
  start: object(pointFields).required(),
  end: object(pointFields).required(),
  hours: text(),
  raw_hours: text(),
  reset_applied: bool(),
  inconsistent: bool(),
  review: oneOf(READING_REVIEWS),
  opened_at: text(),
  age_days: int(),
  overlapping_job_ids: idList(),
  segments: array(segmentSchema).required(),
});

const totalsFields = {
  total_hours: text(),
  customer_work_hours: text(),
  non_revenue_hours: text(),
  unallocated_hours: text(),
  unexplained_hours: text(),
  proposed_hours: text(),
  approved_non_customer_hours: text(),
  identified_variance_hours: text(),
  pending_review_hours: text(),
};
export const engineHourTotalsSchema: Schema<EngineHourTotalsDto> = object(totalsFields);

const overlapSchema: Schema<JobOverlapDto> = object({
  first_job_id: id(),
  second_job_id: id(),
  basis: text(),
});

export const machineEngineHoursSchema: Schema<MachineEngineHoursDto> = object({
  machine_id: id(),
  machine_code: text(),
  machine_name: text(),
  status: oneOf(RECONCILIATION_STATUSES),
  baseline: object(baselineFields).nullable().defined(),
  baseline_proposal: object(baselineFields).nullable().defined(),
  intervals: array(intervalSchema).required(),
  totals: object(totalsFields).required(),
  overlaps: array(overlapSchema).required(),
  policy_version: text(),
});

export const machineEngineHoursSummarySchema: Schema<MachineEngineHoursSummaryDto> = object({
  machine_id: id(),
  machine_code: text(),
  machine_name: text(),
  status: oneOf(RECONCILIATION_STATUSES),
  baseline_reading: nullableText(),
  baseline_pending: bool(),
  last_reading: nullableText(),
  last_reading_at: nullableText(),
  totals: object(totalsFields).required(),
  open_items: int(),
  oldest_open_item_days: nullableInt(),
});

export const unallocatedSegmentSchema: Schema<UnallocatedSegmentDto> = object({
  machine_id: id(),
  machine_code: text(),
  machine_name: text(),
  start: object(pointFields).required(),
  end: object(pointFields).required(),
  hours: text(),
  review: oneOf(READING_REVIEWS),
  classification: oneOf(SEGMENT_CLASSIFICATIONS),
  opened_at: text(),
  age_days: int(),
  investigation_due: bool(),
  approved: nullableRef(),
  proposal: nullableRef(),
});

export const classificationSchema: Schema<ClassificationDto> = object({
  id: id(),
  machine_id: id(),
  machine_code: optionalText(),
  start_ref: id(),
  end_ref: id(),
  start_at: text(),
  end_at: text(),
  hours: text(),
  outcome: oneOf(CLASSIFICATION_OUTCOMES),
  reason_id: id(),
  reason_name: optionalText(),
  note: text(),
  status: oneOf(PROPOSAL_STATUSES),
  proposed_by: nullableId(),
  proposed_by_name: optionalText(),
  proposed_at: text(),
  decided_by: nullableId(),
  decided_by_name: optionalText(),
  decided_at: nullableText(),
  decision_note: nullableText(),
  policy_version: text(),
});

export const correctionSchema: Schema<CorrectionDto> = object({
  id: id(),
  machine_id: id(),
  machine_code: optionalText(),
  job_id: nullableId(),
  superseded_capture_id: id(),
  replacement_capture_id: id(),
  old_reading: text(),
  new_reading: text(),
  reason: text(),
  status: oneOf(PROPOSAL_STATUSES),
  proposed_by: nullableId(),
  proposed_by_name: optionalText(),
  proposed_at: text(),
  decided_by: nullableId(),
  decided_by_name: optionalText(),
  decided_at: nullableText(),
  decision_note: nullableText(),
  policy_version: text(),
});
