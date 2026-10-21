import type { CaptureMode, CaptureResultDto, JobDto, ReadingKind } from '../../../api/types';
import { humanize } from '../../../utils/text';

/** The METER_CAPTURE values the console needs, read defensively from the free-form policy values. */
export interface CapturePolicyView {
  requiredMode: CaptureMode | null;
  manualPhotoRequired: boolean | null;
  gpsEnforcement: string | null;
  gpsMaxAccuracyM: number | null;
  gpsMaxAgeSeconds: number | null;
}

const mode = (v: unknown): CaptureMode | null => (v === 'AUTOMATIC' || v === 'MANUAL' ? v : null);

export function readCapturePolicy(
  values: Record<string, unknown>,
  kind: ReadingKind,
): CapturePolicyView {
  const bool = (v: unknown) => (typeof v === 'boolean' ? v : null);
  const num = (v: unknown) => (typeof v === 'number' ? v : null);
  return {
    requiredMode: mode(kind === 'OPENING' ? values.opening_mode : values.closing_mode),
    manualPhotoRequired: bool(values.manual_photo_required),
    gpsEnforcement: typeof values.gps_enforcement === 'string' ? values.gps_enforcement : null,
    gpsMaxAccuracyM: num(values.gps_max_accuracy_m),
    gpsMaxAgeSeconds: num(values.gps_max_age_seconds),
  };
}

/** Whether a photo is expected for this mode under the policy (AUTOMATIC always needs one). */
export function photoExpected(policy: CapturePolicyView | null, used: CaptureMode | ''): boolean {
  if (used === 'AUTOMATIC') return true;
  return used === 'MANUAL' && policy?.manualPhotoRequired === true;
}

/** Device id recorded for readings captured from the web console. */
export const CONSOLE_DEVICE_ID = 'web-console';

export function readingKindFor(job: JobDto): ReadingKind | null {
  if (job.status === 'APPROVED') return 'OPENING';
  if (job.status === 'IN_PROGRESS') return 'CLOSING';
  return null;
}

export function resultMessage(r: CaptureResultDto): string {
  const state = humanize(r.capture.state);
  const n = r.findings.length;
  return n === 0
    ? `Reading recorded (${state}).`
    : `Reading recorded (${state}); ${String(n)} finding(s) require review.`;
}
