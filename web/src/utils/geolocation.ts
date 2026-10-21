import type { GpsIn } from '../api/types';

/** Provider label recorded with console GPS attempts. */
export const BROWSER_GPS_PROVIDER = 'browser';

/** Browser attempt budget (a UI wait limit, not a business threshold; the policy judges freshness). */
export const GPS_ATTEMPT_TIMEOUT_MS = 20_000;

// GeolocationPositionError codes (W3C); constants on the error object are not always present.
const PERMISSION_DENIED = 1;
const TIMEOUT = 3;

/**
 * Attempt one fresh fix with the browser Geolocation API and report its real outcome. On failure only
 * the status is returned — coordinates are never invented or reused.
 */
export function attemptGpsFix(timeoutMs = GPS_ATTEMPT_TIMEOUT_MS): Promise<GpsIn> {
  if (!('geolocation' in navigator)) {
    return Promise.resolve({ status: 'DISABLED', provider: BROWSER_GPS_PROVIDER });
  }
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        resolve({
          status: 'FIX',
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy_m: pos.coords.accuracy,
          captured_at: new Date(pos.timestamp).toISOString(),
          provider: BROWSER_GPS_PROVIDER,
        });
      },
      (err) => {
        const status =
          err.code === PERMISSION_DENIED
            ? 'PERMISSION_DENIED'
            : err.code === TIMEOUT
              ? 'TIMEOUT'
              : 'NO_FIX';
        resolve({ status, provider: BROWSER_GPS_PROVIDER });
      },
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 0 },
    );
  });
}
