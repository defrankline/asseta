/** Runtime (Yup) response schemas for meter captures, evidence attachments, exceptions and resets. */
import { array, object, type Schema } from 'yup';
import type {
  AttachmentDto,
  CaptureResultDto,
  CaptureState,
  ExceptionDto,
  ExceptionStatus,
  ExceptionType,
  FindingDto,
  GpsStatus,
  MeterCaptureDto,
  PhotoUrlDto,
  ReadingKind,
  ResetDto,
} from '../types';
import {
  bool,
  id,
  int,
  nullableId,
  nullableNum,
  nullableRecord,
  nullableText,
  oneOf,
  record,
  text,
} from './schemaKit';

export const CAPTURE_STATES: readonly CaptureState[] = [
  'ACCEPTED',
  'PROVISIONAL',
  'REJECTED',
  'SUPERSEDED',
];
export const GPS_STATUSES: readonly GpsStatus[] = [
  'FIX',
  'NO_FIX',
  'TIMEOUT',
  'PERMISSION_DENIED',
  'DISABLED',
];
export const READING_KINDS: readonly ReadingKind[] = ['OPENING', 'CLOSING', 'DAILY'];
export const EXCEPTION_STATUSES: readonly ExceptionStatus[] = ['OPEN', 'EXPLAINED', 'CONFIRMED'];
export const EXCEPTION_TYPES: readonly ExceptionType[] = [
  'GPS_UNAVAILABLE',
  'GPS_INACCURATE',
  'GPS_STALE',
  'LOCATION_MISMATCH',
  'MODE_POLICY_VIOLATION',
  'PHOTO_MISSING',
  'LOW_OCR_CONFIDENCE',
  'MANUAL_CORRECTION',
  'METER_DECREASE',
  'IMPOSSIBLE_INCREMENT',
  'CONTINUITY_GAP',
  'DUPLICATE_IMAGE',
  'TELEMETRY_MISMATCH',
  'CLOCK_SKEW',
  'POLICY_SNAPSHOT_UNVERIFIED',
  'MISSING_DAILY_REPORT',
  'UNEXPLAINED_HOURS',
  'OVERLAPPING_ALLOCATION',
];

export const attachmentSchema: Schema<AttachmentDto> = object({
  id: id(),
  sha256: text(),
  content_type: text(),
  size_bytes: int(),
  purpose: text(),
  uploaded_at: text(),
});

export const photoUrlSchema: Schema<PhotoUrlDto> = object({
  url: text(),
  expires_in_seconds: int(),
});

const captureFields = {
  id: id(),
  job_id: nullableId(),
  machine_id: id(),
  kind: oneOf(READING_KINDS),
  capture_mode: text(),
  reading: text(),
  ocr_value: nullableText(),
  ocr_confidence: nullableNum(),
  manually_corrected: bool(),
  photo_attachment_id: nullableId(),
  photo_sha256: nullableText(),
  gps_status: oneOf(GPS_STATUSES),
  latitude: nullableNum(),
  longitude: nullableNum(),
  accuracy_m: nullableNum(),
  location_captured_at: nullableText(),
  captured_at: text(),
  received_at: text(),
  policy_version: text(),
  state: oneOf(CAPTURE_STATES),
  tracker_comparison: nullableRecord(),
  supersedes_id: nullableId(),
};

export const meterCaptureSchema: Schema<MeterCaptureDto> = object(captureFields);

export const findingSchema: Schema<FindingDto> = object({
  type: oneOf(EXCEPTION_TYPES),
  severity: text(),
  blocking: bool(),
  evidence: record(),
});

export const captureResultSchema: Schema<CaptureResultDto> = object({
  capture: object(captureFields).required(),
  findings: array(findingSchema).required(),
});

export const exceptionSchema: Schema<ExceptionDto> = object({
  id: id(),
  job_id: nullableId(),
  machine_id: id(),
  meter_capture_id: nullableId(),
  exception_type: oneOf(EXCEPTION_TYPES),
  severity: text(),
  blocking: bool(),
  evidence: record(),
  policy_version: nullableText(),
  status: oneOf(EXCEPTION_STATUSES),
  review_note: nullableText(),
  reviewed_at: nullableText(),
  created_at: text(),
});

export const resetSchema: Schema<ResetDto> = object({
  id: id(),
  machine_id: id(),
  old_reading: text(),
  new_reading: text(),
  effective_at: text(),
  reason: text(),
  evidence_attachment_id: nullableId(),
  status: text(),
  requested_by: nullableId(),
  decided_at: nullableText(),
});
