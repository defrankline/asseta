/** Runtime (Yup) response schemas for revenue reconciliation (DEC-031 R1–R3). */
import { array, mixed, object, string, type Schema } from 'yup';
import type {
  DailyMachineSheetDetailDto,
  DailyMachineSheetRowDto,
  NonRevenueActivityDto,
  NonRevenueApprovalDto,
  RevenueAdjustmentDto,
  RevenueDifferenceDto,
  RevenueDifferenceStatus,
  RevenueReasonDto,
  SheetFlag,
  SheetFlagRefDto,
  SheetFuelDto,
  SheetJobDto,
  SheetMoneyDto,
  SheetMoneySourceDto,
  SheetReadingDto,
  SheetSegmentDto,
} from '../types';
import { bool, id, int, nullableId, nullableText, oneOf, record, text } from './schemaKit';

export const SHEET_FLAGS: readonly SheetFlag[] = [
  'MISSING_DAILY_REPORT',
  'UNEXPLAINED_HOURS',
  'ENGINE_ON_WITHOUT_JOB',
  'FUEL_ABOVE_NORM',
  'REVENUE_DIFFERENCE',
];

export const DIFFERENCE_STATUSES: readonly RevenueDifferenceStatus[] = [
  'OPEN',
  'EXPLANATION_PROPOSED',
  'EXPLAINED',
  'CONFIRMED',
  'CLEARED',
];

export const MONEY_SOURCES: readonly SheetMoneySourceDto['source'][] = [
  'INVOICE_LINE',
  'PREPAID_CONSUMPTION',
];

export const ACTIVITY_APPROVAL_STATUSES: readonly NonRevenueActivityDto['approval_status'][] = [
  'NONE',
  'PROPOSED',
  'APPROVED',
  'REJECTED',
];

const optionalText = () => nullableText().optional();
/** Decimal the server always sends (defaulted to 0 should an older server omit it). */
const optionalDecimal = () => string().defined().default('0');

/** `{ "MOBILIZATION": "1.50", … }`: hours per work-log type. */
const hoursByType = () =>
  mixed<Record<string, string>>(
    (v): v is Record<string, string> =>
      typeof v === 'object' &&
      v !== null &&
      !Array.isArray(v) &&
      Object.values(v as Record<string, unknown>).every((h) => typeof h === 'string'),
  ).required();

const moneySchema: Schema<SheetMoneyDto> = object({
  currency: text(),
  expected: text(),
  in_progress: text(),
  attributed: text(),
  difference: text(),
  unexplained_hours: optionalDecimal(),
  unexplained_expected: optionalDecimal(),
});

const jobSchema: Schema<SheetJobDto> = object({
  job_id: id(),
  job_number: optionalText(),
  billing_mode: text(),
  status: text(),
  customer_id: nullableId().optional(),
  customer_name: optionalText(),
  job_site_id: nullableId().optional(),
  job_site_name: optionalText(),
  customer_work_hours: text(),
  revenue_hours: text(),
});

const rowFields = {
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  day: text(),
  first_reading: nullableText(),
  last_reading: nullableText(),
  reading_count: int(),
  engine_hours: text(),
  customer_work_hours: text(),
  non_revenue_hours: text(),
  non_revenue_by_type: hoursByType(),
  non_revenue_pending_hours: optionalDecimal(),
  revenue_hours: text(),
  approved_non_customer_hours: text(),
  identified_variance_hours: text(),
  unexplained_hours: text(),
  pending_review_hours: text(),
  fuel_litres: text(),
  jobs: array(jobSchema).required(),
  money: array(moneySchema).required(),
  flags: array(oneOf(SHEET_FLAGS)).required(),
};

export const sheetRowSchema: Schema<DailyMachineSheetRowDto> = object(rowFields);

const readingSchema: Schema<SheetReadingDto> = object({
  id: id(),
  kind: text(),
  captured_at: text(),
  reading: text(),
  state: text(),
  job_id: nullableId(),
  job_number: optionalText(),
});

const segmentSchema: Schema<SheetSegmentDto> = object({
  start_ref: text(),
  end_ref: text(),
  start_at: text(),
  end_at: text(),
  kind: text(),
  classification: text(),
  review: text(),
  hours_in_day: text(),
  customer_work_hours_in_day: text(),
  non_revenue_by_type: hoursByType(),
  job_id: nullableId(),
  job_number: optionalText(),
});

const moneySourceSchema: Schema<SheetMoneySourceDto> = object({
  source: oneOf(MONEY_SOURCES),
  ref_id: id(),
  parent_id: id(),
  job_id: id(),
  job_number: optionalText(),
  currency: text(),
  amount: text(),
  hours: nullableText(),
});

const flagRefSchema: Schema<SheetFlagRefDto> = object({
  flag: oneOf(SHEET_FLAGS),
  record_type: text(),
  record_id: id(),
});

const fuelSchema: Schema<SheetFuelDto> = object({
  id: id(),
  event_type: text(),
  litres: text(),
  occurred_at: text(),
  job_id: nullableId(),
});

export const sheetDetailSchema: Schema<DailyMachineSheetDetailDto> = object({
  ...rowFields,
  readings: array(readingSchema).required(),
  segments: array(segmentSchema).required(),
  money_sources: array(moneySourceSchema).required(),
  flag_records: array(flagRefSchema).required(),
  fuel_events: array(fuelSchema).required(),
});

export const revenueReasonSchema: Schema<RevenueReasonDto> = object({
  id: id(),
  code: text(),
  name: text(),
  description: nullableText(),
  is_active: bool(),
  version: int(),
  deactivated_at: optionalText(),
  deactivation_reason: optionalText(),
});

const adjustmentSchema: Schema<RevenueAdjustmentDto> = object({
  id: id(),
  previous_difference: text(),
  new_difference: text(),
  amount: text(),
  cause_type: text(),
  cause_id: id(),
  created_by: nullableId(),
  created_by_name: optionalText(),
  created_at: text(),
});

export const revenueDifferenceSchema: Schema<RevenueDifferenceDto> = object({
  id: id(),
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  period_kind: text(),
  period_key: text(),
  period_start: text(),
  period_end: text(),
  local_from: text(),
  local_to: text(),
  job_id: nullableId(),
  job_number: optionalText(),
  currency: text(),
  expected_amount: text(),
  in_progress_amount: text(),
  attributed_amount: text(),
  difference: text(),
  customer_work_hours: text(),
  non_revenue_hours: text(),
  unexplained_hours: text(),
  unexplained_expected_amount: text(),
  detail: record(),
  status: oneOf(DIFFERENCE_STATUSES),
  case_id: nullableId(),
  case_number: optionalText(),
  policy_version: text(),
  opened_at: text(),
  computed_at: text(),
  reason_id: nullableId(),
  reason_name: optionalText(),
  explanation_note: nullableText(),
  explained_by: nullableId(),
  explained_by_name: optionalText(),
  explained_at: nullableText(),
  decided_by: nullableId(),
  decided_by_name: optionalText(),
  decided_at: nullableText(),
  decision_note: nullableText(),
  adjustments: array(adjustmentSchema).optional(),
  adjusted_difference: optionalText(),
});

export const nonRevenueActivitySchema: Schema<NonRevenueActivityDto> = object({
  activity_id: id(),
  job_id: id(),
  job_number: optionalText(),
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  activity_type: text(),
  started_at: text(),
  ended_at: text(),
  hours: text(),
  note: nullableText(),
  approval_id: nullableId(),
  approval_status: oneOf(ACTIVITY_APPROVAL_STATUSES),
});

export const nonRevenueApprovalSchema: Schema<NonRevenueApprovalDto> = object({
  id: id(),
  activity_id: id(),
  job_id: id(),
  job_number: optionalText(),
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  activity_type: text(),
  started_at: text(),
  ended_at: text(),
  hours: text(),
  reason_id: id(),
  reason_name: optionalText(),
  note: text(),
  status: text(),
  proposed_by: nullableId(),
  proposed_by_name: optionalText(),
  proposed_at: text(),
  decided_by: nullableId(),
  decided_by_name: optionalText(),
  decided_at: nullableText(),
  decision_note: nullableText(),
  policy_version: text(),
});
