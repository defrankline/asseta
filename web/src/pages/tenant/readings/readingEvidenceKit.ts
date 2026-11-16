import { useCallback, useEffect, useState } from 'react';
import { mixed, string } from 'yup';
import { ApiError } from '../../../api/ApiError';
import { meterService } from '../../../api/services/meterService';
import type { AttachmentDto, CaptureMode, GpsIn } from '../../../api/types';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { attemptGpsFix } from '../../../utils/geolocation';

/**
 * Evidence pieces shared by every reading recorded from a browser: job readings, DAILY readings,
 * baseline proposals and reading corrections. Coordinates are never invented: the browser's real
 * GPS outcome is submitted, and photos are uploaded unchanged (the server keeps the hash).
 */

/** Meter reading as shown on the meter (up to 4 decimals). */
export const readingField = () =>
  string()
    .trim()
    .required('Reading is required')
    .matches(/^\d+(\.\d{1,4})?$/, 'Enter the meter reading as shown (up to 4 decimals)');

export const captureModeField = () =>
  mixed<CaptureMode | ''>()
    .oneOf(['AUTOMATIC', 'MANUAL'], 'Choose the capture mode')
    .required('Choose the capture mode');

export const CAPTURE_MODE_OPTIONS = [
  { value: 'AUTOMATIC', label: 'Automatic (photo; no OCR runs in the console)' },
  { value: 'MANUAL', label: 'Manual (numeric entry)' },
];

/** One GPS attempt on open, with a retry; null while the browser is still trying. */
export function useBrowserGps(): { gps: GpsIn | null; retry: () => void } {
  const [gps, setGps] = useState<GpsIn | null>(null);
  useEffect(() => {
    let active = true;
    void attemptGpsFix().then((r) => {
      if (active) setGps(r);
    });
    return () => {
      active = false;
    };
  }, []);
  const retry = useCallback(() => {
    setGps(null);
    void attemptGpsFix().then(setGps);
  }, []);
  return { gps, retry };
}

/** Thrown from a submit while the GPS attempt is still running (keeps the dialog open). */
export function gpsPendingError(): ApiError {
  return new ApiError({
    status: null,
    code: 'gps_pending',
    message: 'Wait for the GPS attempt to finish before submitting.',
    correlationId: null,
  });
}

/** Uploads a meter photo once per picked file (retries reuse the idempotency key). */
export function useMeterPhotoUpload(): (file: File) => Promise<AttachmentDto> {
  const uploadKey = useIdempotencyKey();
  return (file: File) =>
    meterService.upload(
      file,
      'METER_PHOTO',
      uploadKey({ name: file.name, size: file.size, modified: file.lastModified }),
    );
}
