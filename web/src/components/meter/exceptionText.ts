/**
 * Plain-language labels and explanations for meter/GPS exception types. Exceptions are evidence for
 * human review — the wording is deliberately neutral ("requires review") and never a verdict.
 */
import type { ExceptionType } from '../../api/types';

export const NEUTRAL_REVIEW_NOTICE =
  'Exceptions are recorded evidence that requires review. They are not a conclusion about any person.';

export const EXCEPTION_TYPE_LABELS: Readonly<Record<ExceptionType, string>> = {
  GPS_UNAVAILABLE: 'GPS unavailable',
  GPS_INACCURATE: 'GPS inaccurate',
  GPS_STALE: 'GPS fix not fresh',
  LOCATION_MISMATCH: 'Location differs from tracker',
  MODE_POLICY_VIOLATION: 'Capture mode differs from policy',
  PHOTO_MISSING: 'Meter photo missing',
  LOW_OCR_CONFIDENCE: 'Low OCR confidence',
  MANUAL_CORRECTION: 'Reading differs from OCR',
  METER_DECREASE: 'Meter reading decreased',
  IMPOSSIBLE_INCREMENT: 'Increment exceeds elapsed time',
  CONTINUITY_GAP: 'Gap since previous job',
  DUPLICATE_IMAGE: 'Photo reused',
  TELEMETRY_MISMATCH: 'Differs from tracker engine hours',
  CLOCK_SKEW: 'Device clock ahead of server',
  POLICY_SNAPSHOT_UNVERIFIED: 'Offline policy not confirmed',
  HOURS_OVERRUN: 'Hours beyond what the customer has active',
  MISSING_DAILY_REPORT: 'Daily report missing',
  UNEXPLAINED_HOURS: 'Engine hours not yet explained',
  OVERLAPPING_ALLOCATION: 'Job intervals overlap',
};

/** Labels (with units) for evidence keys; unknown keys fall back to a humanised key. */
export const EVIDENCE_KEY_LABELS: Readonly<Record<string, string>> = {
  gps_status: 'GPS result',
  enforcement: 'GPS enforcement',
  accuracy_m: 'Phone accuracy (m)',
  max_accuracy_m: 'Allowed accuracy (m)',
  location_age_s: 'Location age (s)',
  max_age_s: 'Allowed age (s)',
  compared: 'Compared with tracker',
  reason: 'Reason',
  distance_m: 'Distance phone ↔ tracker (m)',
  allowed_m: 'Allowed distance (m)',
  tracker_time: 'Tracker position time',
  time_offset_s: 'Time offset (s)',
  required_mode: 'Required mode',
  used_mode: 'Mode used',
  mode: 'Capture mode',
  ocr_confidence: 'OCR confidence',
  minimum: 'Minimum confidence',
  ocr_value: 'OCR value',
  entered_value: 'Entered value',
  previous_reading: 'Previous reading',
  previous_at: 'Previous reading time',
  previous_job_id: 'Previous job',
  reading: 'Reading',
  delta_hours: 'Meter increase (h)',
  elapsed_hours: 'Elapsed time (h)',
  gap_hours: 'Gap (h)',
  tolerance_hours: 'Tolerance (h)',
  sha256: 'Photo SHA-256',
  meter_delta: 'Meter hours',
  tracker_engine_hours_delta: 'Tracker engine hours',
  tolerance: 'Tolerance (h)',
  device_time: 'Device time',
  server_time: 'Server receive time',
  device_id: 'Device',
  captured_at: 'Reading time',
  policy_version_ids: 'Policy versions applied',
  issued_at: 'Policy issued to device',
  valid_until: 'Policy valid until',
};

/** Display any evidence value verbatim (numbers/strings unchanged, never re-computed). */
export function evidenceText(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

type Explainer = (get: (key: string) => string) => string;

const EXPLAIN: Readonly<Record<ExceptionType, Explainer>> = {
  GPS_UNAVAILABLE: (g) =>
    `No valid GPS fix was recorded with this reading (result: ${g('gps_status')}). ` +
    `Under ${g('enforcement')} enforcement the reading is kept for review; coordinates are never substituted.`,
  GPS_INACCURATE: (g) =>
    `Phone GPS accuracy was ${g('accuracy_m')} m; the policy allows at most ${g('max_accuracy_m')} m.`,
  GPS_STALE: (g) =>
    `The GPS fix was ${g('location_age_s')} s away from the reading time; the policy allows ${g('max_age_s')} s.`,
  LOCATION_MISMATCH: (g) =>
    `Phone fix ${g('distance_m')} m from the machine tracker position at the same time ` +
    `(offset ${g('time_offset_s')} s); allowed ${g('allowed_m')} m.`,
  MODE_POLICY_VIOLATION: (g) =>
    `The policy requires ${g('required_mode')} capture for this reading; ${g('used_mode')} was used.`,
  PHOTO_MISSING: (g) =>
    `No meter photo was attached, but the policy requires one for ${g('mode')} capture.`,
  LOW_OCR_CONFIDENCE: (g) =>
    `On-device OCR confidence was ${g('ocr_confidence')}; the policy minimum is ${g('minimum')}.`,
  MANUAL_CORRECTION: (g) => `OCR read ${g('ocr_value')} but ${g('entered_value')} was entered.`,
  METER_DECREASE: (g) =>
    `Reading ${g('reading')} is lower than the machine's previous valid reading ${g('previous_reading')} ` +
    `(${g('previous_at')}). An approved meter reset would explain a legitimate decrease.`,
  IMPOSSIBLE_INCREMENT: (g) =>
    `The meter advanced ${g('delta_hours')} h in ${g('elapsed_hours')} h of elapsed time, ` +
    `more than the policy allows per elapsed hour.`,
  CONTINUITY_GAP: (g) =>
    `The opening reading is ${g('gap_hours')} h above the previous closing reading ` +
    `${g('previous_reading')}; tolerance ${g('tolerance_hours')} h.`,
  DUPLICATE_IMAGE: (g) =>
    `The same photo (SHA-256 ${g('sha256').slice(0, 12)}…) is attached to another capture.`,
  TELEMETRY_MISMATCH: (g) =>
    `Meter advanced ${g('meter_delta')} h while the tracker reported ${g('tracker_engine_hours_delta')} ` +
    `engine hours; tolerance ${g('tolerance')} h.`,
  CLOCK_SKEW: (g) =>
    `Device time ${g('device_time')} is ahead of server receive time ${g('server_time')} beyond tolerance.`,
  POLICY_SNAPSHOT_UNVERIFIED: (g) =>
    g('reason') === 'OUTSIDE_VALIDITY'
      ? `The offline policy the device applied was valid from ${g('issued_at')} until ${g('valid_until')}; ` +
        `the reading was taken at ${g('captured_at')}.`
      : `The offline policy the device applied was not issued to device ${g('device_id')}.`,
  HOURS_OVERRUN: (g) =>
    g('drawdown') === 'DAILY'
      ? `On ${g('day')} the job had used ${g('billable_hours_to_date')} billable hours to date; ` +
        `${g('excess_hours')} of them were not covered by the customer's activated hours on this machine ` +
        `(drawn day by day). New activated hours cover them, or the final allocation at completion replaces this.`
      : `${g('excess_hours')} of ${g('billable_hours')} billable hours were not covered by the customer's activated ` +
        `hours on this machine; new activated hours cover them, or a reviewer records the outcome.`,
  MISSING_DAILY_REPORT: (g) =>
    `The machine worked on ${g('day')} but no meter reading was recorded before ${g('cutoff_hour')}:00 ` +
    `(basis: ${g('basis')}).`,
  UNEXPLAINED_HOURS: (g) =>
    `${g('hours')} engine hours between readings ${g('start_reading')} and ${g('end_reading')} are not ` +
    `allocated to a job and not yet explained.`,
  OVERLAPPING_ALLOCATION: (g) =>
    `Two jobs claim the same engine hours (${g('basis')}); each hour is counted once, for the earlier job.`,
};

/** One-sentence, neutral explanation of an exception from its recorded evidence. */
export function explainException(type: ExceptionType, evidence: Record<string, unknown>): string {
  return EXPLAIN[type]((key) => evidenceText(evidence[key]));
}
