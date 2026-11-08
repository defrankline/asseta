/** Runtime (Yup) schemas of the work allocation ledger and the daily operational report (DEC-032 Phase 1). */
import { array, object, string, type Schema } from 'yup';
import type {
  AllocationCorrectionDto,
  AllocationDayDto,
  AllocationKind,
  AllocationLotDto,
  AllocationSource,
  AllocationStatus,
  DailyReportDto,
  DailyReportPrefillDto,
  DailyReportStatus,
  ReportAllocationDto,
  UnbillableLineDto,
  WorkAllocationDto,
} from '../allocationTypes';
import { bool, id, idList, int, nullableId, nullableText, oneOf, text } from './schemaKit';

export const ALLOCATION_KINDS: readonly AllocationKind[] = [
  'CUSTOMER_WORK',
  'AUTHORIZED_ACTIVITY',
  'UNEXPLAINED',
];
export const ALLOCATION_STATUSES: readonly AllocationStatus[] = [
  'PROPOSED',
  'ACTIVE',
  'SUPERSEDED',
  'REJECTED',
];
export const ALLOCATION_SOURCES: readonly AllocationSource[] = [
  'DERIVED',
  'BACKFILL',
  'CORRECTION',
];
export const DAILY_REPORT_STATUSES: readonly DailyReportStatus[] = [
  'SUBMITTED',
  'REVIEWED',
  'RETURNED',
  'SUPERSEDED',
];

const optionalText = () => nullableText().optional();

const lotSchema: Schema<AllocationLotDto> = object({
  purchase_id: id(),
  purchase_number: optionalText(),
  hours: text(),
});

export const workAllocationSchema: Schema<WorkAllocationDto> = object({
  id: id(),
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  work_date: text(),
  meter_epoch: int(),
  start_ref: id(),
  start_reading: text(),
  start_at: text(),
  end_ref: id(),
  end_reading: text(),
  end_at: text(),
  hours: text(),
  kind: oneOf(ALLOCATION_KINDS),
  customer_id: nullableId(),
  customer_name: optionalText(),
  job_id: nullableId(),
  job_number: optionalText(),
  activity_type: nullableText(),
  reason_id: nullableId(),
  reason_name: optionalText(),
  lots: array(lotSchema).required(),
  evidence_attachment_ids: idList(),
  source: oneOf(ALLOCATION_SOURCES),
  reading_review: text(),
  changeover_id: nullableId(),
  classification_id: nullableId(),
  status: oneOf(ALLOCATION_STATUSES),
  supersedes_id: nullableId(),
  superseded_by_ids: array(string().required()).optional(),
  correction_group_id: nullableId(),
  correction_reason: nullableText(),
  recorded_by: nullableId(),
  recorded_by_name: optionalText(),
  decided_by: nullableId(),
  decided_by_name: optionalText(),
  decided_at: nullableText(),
  decision_note: nullableText(),
  superseded_at: nullableText(),
  policy_version: text(),
  created_at: text(),
});

export const allocationDaySchema: Schema<AllocationDayDto> = object({
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  day: text(),
  total_engine_hours: text(),
  customer_hours: text(),
  authorized_hours: text(),
  unexplained_hours: text(),
  allocated_hours: text(),
  difference_hours: text(),
  reconciled: bool(),
});

export const allocationCorrectionSchema: Schema<AllocationCorrectionDto> = object({
  group_id: id(),
  status: oneOf(ALLOCATION_STATUSES),
  supersedes_id: nullableId(),
  entries: array(workAllocationSchema).required(),
});

const unbillableSchema: Schema<UnbillableLineDto> = object({
  reason_id: id(),
  reason_name: optionalText(),
  hours: text(),
});

const reportAllocationSchema: Schema<ReportAllocationDto> = object({
  allocation_id: id(),
  kind: oneOf(ALLOCATION_KINDS),
  customer_id: nullableId(),
  customer_name: optionalText(),
  job_id: nullableId(),
  job_number: optionalText(),
  activity_type: nullableText(),
  start_reading: text(),
  end_reading: text(),
  hours: text(),
});

export const dailyReportSchema: Schema<DailyReportDto> = object({
  id: id(),
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  report_date: text(),
  opening_ref: id(),
  opening_reading: text(),
  closing_ref: id(),
  closing_reading: text(),
  total_hours: text(),
  billable_hours: text(),
  unbillable_hours: text(),
  difference_hours: text(),
  unbillable: array(unbillableSchema).required(),
  allocations: array(reportAllocationSchema).required(),
  evidence_attachment_ids: idList(),
  note: nullableText(),
  status: oneOf(DAILY_REPORT_STATUSES),
  supersedes_id: nullableId(),
  is_duplicate: bool(),
  duplicate_of_id: nullableId(),
  is_late: bool(),
  submitted_by: nullableId(),
  submitted_by_name: optionalText(),
  submitted_at: text(),
  client_created_at: text(),
  reviewed_by: nullableId(),
  reviewed_by_name: optionalText(),
  reviewed_at: nullableText(),
  review_note: nullableText(),
  source: text(),
  policy_version: text(),
});

export const dailyReportPrefillSchema: Schema<DailyReportPrefillDto> = object({
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  report_date: text(),
  opening_ref: nullableId(),
  opening_reading: nullableText(),
  opening_at: nullableText(),
  closing_ref: nullableId(),
  closing_reading: nullableText(),
  closing_at: nullableText(),
  total_hours: nullableText(),
  customer_hours: text(),
  authorized_hours: text(),
  unexplained_hours: text(),
  allocations: array(reportAllocationSchema).required(),
  existing_report_ids: idList(),
});
