/**
 * Runtime (Yup) response schemas for machine reports (ADR-008): reports and their lines, the tracker
 * cross-check, per-machine report status, the form context, available hours and the reason list.
 */
import { array, mixed, number, object, string, type Schema } from 'yup';
import type {
  AvailableHoursDto,
  LotDto,
  MachineReportContextDto,
  MachineReportDto,
  MachineReportLineDto,
  MachineReportReasonDto,
  MachineReportStatus,
  MachineReportStatusDto,
  ReportLineKind,
  StartSource,
  TrackerCheckDto,
} from '../machineReportTypes';
import { findingSchema } from './meterSchemas';
import { bool, id, int, nullableId, nullableOneOf, nullableText, oneOf, text } from './schemaKit';

const optionalText = () => string().nullable().default(null);
/** Newer optional fields (older servers and cached rows may not send them). */
const maybeText = () => string().nullable().optional();
const maybeNum = () => number().nullable().optional();

/** The machine's last visit (status and context): its reading's time, place and GPS point. */
const lastVisitFields = {
  last_visit_at: maybeText(),
  last_visit_lat: maybeNum(),
  last_visit_lng: maybeNum(),
  last_visit_accuracy_m: maybeNum(),
  last_visit_place: maybeText(),
  last_visit_site_name: maybeText(),
};

export const MACHINE_REPORT_STATUSES: readonly MachineReportStatus[] = [
  'SUBMITTED',
  'APPROVED',
  'REJECTED',
];
export const REPORT_LINE_KINDS: readonly ReportLineKind[] = ['CUSTOMER', 'NON_PRODUCTIVE'];
export const START_SOURCES: readonly StartSource[] = ['REPORT', 'BASELINE', 'RESET', 'OPENING'];

export const machineReportReasonSchema: Schema<MachineReportReasonDto> = object({
  id: id(),
  code: text(),
  name: text(),
  description: nullableText(),
  is_active: bool(),
  version: int(),
});

export const availableHoursSchema: Schema<AvailableHoursDto> = object({
  customer_id: id(),
  customer_name: optionalText(),
  machine_id: optionalText(),
  remaining: text(),
  reserved: text(),
  available: text(),
});

const lotSchema: Schema<LotDto> = object({
  purchase_id: id(),
  purchase_number: optionalText(),
  machine_id: id(),
  hours: text(),
});

const lineSchema: Schema<MachineReportLineDto> = object({
  id: id(),
  line_no: int(),
  kind: oneOf(REPORT_LINE_KINDS),
  customer_id: nullableId(),
  customer_name: optionalText(),
  reason_id: nullableId(),
  reason_code: optionalText(),
  reason_name: optionalText(),
  hours: text(),
  note: nullableText(),
  available_hours: optionalText(),
  lots: array(lotSchema).optional(),
});

const trackerSchema: Schema<TrackerCheckDto> = object({
  available: bool(),
  tracker_hours: nullableText(),
  meter_hours: text(),
  difference: nullableText(),
  tracker_from_at: optionalText(),
  tracker_to_at: optionalText(),
});

export const machineReportSchema: Schema<MachineReportDto> = object({
  id: id(),
  report_number: text(),
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  capture_id: id(),
  opening: bool().default(false),
  start_source: oneOf(START_SOURCES),
  start_ref: text(),
  start_reading: text(),
  start_at: text(),
  end_reading: text(),
  end_at: text(),
  hours: text(),
  customer_hours: text(),
  non_productive_hours: text(),
  status: oneOf(MACHINE_REPORT_STATUSES),
  corrects_id: nullableId(),
  corrected_by_id: optionalText(),
  note: nullableText(),
  source: text(),
  submitted_by: nullableId(),
  submitted_by_name: optionalText(),
  submitted_at: text(),
  client_created_at: nullableText(),
  decided_by: nullableId(),
  decided_by_name: optionalText(),
  decided_at: nullableText(),
  decision_note: nullableText(),
  policy_version: text(),
  photo_attachment_id: optionalText(),
  capture_state: optionalText(),
  findings: array(findingSchema).optional(),
  tracker: mixed<TrackerCheckDto>()
    .nullable()
    .default(null)
    .test('tracker', 'invalid tracker check', (v) => v == null || trackerSchema.isValidSync(v)),
  lines: array(lineSchema).default([]),
  // Time since the previous visit and where both readings were taken.
  previous_visit_at: maybeText(),
  since_previous_visit_seconds: number().integer().nullable().optional(),
  previous_visit_lat: maybeNum(),
  previous_visit_lng: maybeNum(),
  previous_visit_accuracy_m: maybeNum(),
  previous_visit_place: maybeText(),
  previous_visit_site_name: maybeText(),
  visit_lat: maybeNum(),
  visit_lng: maybeNum(),
  visit_accuracy_m: maybeNum(),
  visit_place: maybeText(),
  visit_site_name: maybeText(),
});

export const machineReportStatusSchema: Schema<MachineReportStatusDto> = object({
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  meter_decimal_places: int().default(1),
  previous_reading: optionalText(),
  previous_at: optionalText(),
  previous_source: nullableOneOf(START_SOURCES).default(null),
  opening_required: bool().default(false),
  last_approved_reading: nullableText(),
  last_approved_at: nullableText(),
  last_report_at: nullableText(),
  days_since_report: int().nullable().defined(),
  pending_report_id: nullableId(),
  pending_report_number: nullableText(),
  rejected_report_id: nullableId(),
  ...lastVisitFields,
});

export const machineReportContextSchema: Schema<MachineReportContextDto> = object({
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  meter_decimal_places: int(),
  previous_reading: nullableText(),
  previous_at: nullableText(),
  previous_source: nullableOneOf(START_SOURCES),
  opening_required: bool().default(false),
  meter_epoch: int(),
  pending_report_id: nullableId(),
  last_report_at: nullableText(),
  hours_scope: oneOf(['CUSTOMER', 'MACHINE'] as const),
  customers: array(availableHoursSchema).required(),
  reasons: array(machineReportReasonSchema).required(),
  ...lastVisitFields,
});
