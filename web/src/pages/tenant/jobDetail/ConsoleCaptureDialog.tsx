import { Alert, Box, Typography } from '@mui/material';
import { useCallback, useEffect, useState } from 'react';
import { mixed, object, string, type ObjectSchema } from 'yup';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { ApiError } from '../../../api/ApiError';
import { newUuid } from '../../../api/ids';
import { meterService } from '../../../api/services/meterService';
import { policyService } from '../../../api/services/policyService';
import type {
  AttachmentDto,
  CaptureMode,
  CaptureResultDto,
  GpsIn,
  JobDto,
  MeterCaptureIn,
  ReadingKind,
} from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { AttachmentUpload } from '../../../components/meter/AttachmentUpload';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useSession } from '../../../session/useSession';
import { attemptGpsFix } from '../../../utils/geolocation';
import { humanize } from '../../../utils/text';
import { withErrorCode } from '../shared/errorHints';
import { JOB_ERROR_HINTS } from '../shared/jobDisplay';
import { CONSOLE_DEVICE_ID, photoExpected, readCapturePolicy } from './capturePolicy';
import { CapturePolicySummary } from './CapturePolicySummary';
import { GpsAttemptPanel } from './GpsAttemptPanel';

interface CaptureValues {
  capture_mode: CaptureMode | '';
  reading: string;
}

const schema: ObjectSchema<CaptureValues> = object({
  capture_mode: mixed<CaptureMode | ''>()
    .oneOf(['AUTOMATIC', 'MANUAL'], 'Choose the capture mode')
    .required('Choose the capture mode'),
  reading: string()
    .trim()
    .required('Reading is required')
    .matches(/^\d+(\.\d{1,4})?$/, 'Enter the meter reading as shown (up to 4 decimals)'),
});

const MODE_OPTIONS = [
  { value: 'AUTOMATIC', label: 'Automatic (photo; no OCR runs in the console)' },
  { value: 'MANUAL', label: 'Manual (numeric entry)' },
];

interface ConsoleCaptureDialogProps {
  job: JobDto;
  kind: ReadingKind;
  onClose: () => void;
  onRecorded: (result: CaptureResultDto) => void;
}

/**
 * Owner/manager fallback for recording a reading from the console (mobile apps are the primary path).
 * The capture `id` is generated once per dialog open so retries never create a second reading, and
 * the browser's real GPS outcome is submitted — coordinates are never invented.
 */
export function ConsoleCaptureDialog({
  job,
  kind,
  onClose,
  onRecorded,
}: ConsoleCaptureDialogProps) {
  const { hasPermission } = useSession();
  const canReadPolicy = hasPermission(PERMISSIONS.tenantPolicyRead);
  const [captureId] = useState(newUuid);
  const [capturedAt] = useState(() => new Date().toISOString());
  const keyFor = useIdempotencyKey();
  const uploadKey = useIdempotencyKey();
  const [gps, setGps] = useState<GpsIn | null>(null);
  const [photo, setPhoto] = useState<AttachmentDto | null>(null);

  useEffect(() => {
    let active = true;
    void attemptGpsFix().then((r) => {
      if (active) setGps(r);
    });
    return () => {
      active = false;
    };
  }, []);
  const retryGps = () => {
    setGps(null);
    void attemptGpsFix().then(setGps);
  };

  const loadPolicy = useCallback(
    (signal: AbortSignal) =>
      policyService.effective(
        'METER_CAPTURE',
        { machine_id: job.machine_id, site_id: job.job_site_id ?? undefined },
        signal,
      ),
    [job.machine_id, job.job_site_id],
  );
  const policy = useAsyncResource(loadPolicy, [], canReadPolicy);
  const view = policy.data === null ? null : readCapturePolicy(policy.data.values, kind);
  const kindLabel = humanize(kind).toLowerCase();

  const upload = (file: File) =>
    meterService.upload(
      file,
      'METER_PHOTO',
      uploadKey({ name: file.name, size: file.size, modified: file.lastModified }),
    );

  return (
    <FormDialog<CaptureValues>
      open
      title={`Record ${kindLabel} reading · ${job.job_number}`}
      initialValues={{ capture_mode: '', reading: '' }}
      validationSchema={schema}
      submitLabel="Submit reading"
      maxWidth="md"
      onClose={onClose}
      onSubmit={async (v) => {
        if (gps === null) {
          throw new ApiError({
            status: null,
            code: 'gps_pending',
            message: 'Wait for the GPS attempt to finish before submitting.',
            correlationId: null,
          });
        }
        const payload: MeterCaptureIn = {
          id: captureId,
          job_id: job.id,
          kind,
          capture_mode: v.capture_mode === '' ? 'MANUAL' : v.capture_mode,
          reading: v.reading.trim(),
          gps,
          device_id: CONSOLE_DEVICE_ID,
          captured_at: capturedAt,
          photo_attachment_id: photo?.id ?? null,
          ocr_value: null,
          ocr_confidence: null,
        };
        try {
          onRecorded(await meterService.submitCapture(payload, keyFor(payload)));
        } catch (err) {
          throw withErrorCode(err, JOB_ERROR_HINTS);
        }
      }}
    >
      {(formik) => (
        <>
          <Alert severity="info">
            Console fallback. Supervisors normally capture readings in the mobile app. The console
            does not run OCR, so an Automatic reading recorded here has no OCR result and will be
            listed for review.
          </Alert>
          <CapturePolicySummary
            resource={canReadPolicy ? policy : null}
            view={view}
            kindLabel={kindLabel}
          />
          <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormikSelectField
              name="capture_mode"
              label="Capture mode"
              options={MODE_OPTIONS}
              required
              helperText={
                view?.requiredMode == null
                  ? undefined
                  : `Policy requires ${humanize(view.requiredMode)} for this reading`
              }
            />
            <FormikTextField
              name="reading"
              label="Meter reading (hours)"
              required
              slotProps={{ htmlInput: { inputMode: 'decimal' } }}
            />
          </Box>
          {view?.requiredMode != null &&
            formik.values.capture_mode !== '' &&
            formik.values.capture_mode !== view.requiredMode && (
              <Alert severity="warning">
                This differs from the policy ({humanize(view.requiredMode)}). The reading will be
                recorded and listed as an exception that requires review.
              </Alert>
            )}
          <AttachmentUpload
            label="Meter photo"
            value={photo}
            onChange={setPhoto}
            upload={upload}
            required={photoExpected(view, formik.values.capture_mode)}
            helperText="The original image is stored unchanged with its SHA-256 hash."
          />
          <Typography variant="subtitle2" component="h3">
            Location
          </Typography>
          <GpsAttemptPanel gps={gps} onRetry={retryGps} />
        </>
      )}
    </FormDialog>
  );
}
