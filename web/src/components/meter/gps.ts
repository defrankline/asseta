import type { GpsStatus } from '../../api/types';

export const GPS_STATUS_LABELS: Readonly<Record<GpsStatus, string>> = {
  FIX: 'GPS fix',
  NO_FIX: 'No fix',
  TIMEOUT: 'Timed out',
  PERMISSION_DENIED: 'Permission denied',
  DISABLED: 'Location disabled',
};

export interface GpsEvidenceValues {
  gps_status: GpsStatus;
  latitude: number | null;
  longitude: number | null;
  accuracy_m: number | null;
  location_captured_at: string | null;
  /** Reading (device) time the location is compared against. */
  captured_at: string;
}

/** Seconds between the reading time and the GPS fix time (positive = fix taken before reading). */
export function locationAgeSeconds(v: GpsEvidenceValues): number | null {
  if (v.location_captured_at === null) return null;
  const fix = Date.parse(v.location_captured_at);
  const reading = Date.parse(v.captured_at);
  if (Number.isNaN(fix) || Number.isNaN(reading)) return null;
  return Math.round((reading - fix) / 1000);
}
