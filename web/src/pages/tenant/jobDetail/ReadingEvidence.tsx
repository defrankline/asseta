import { Alert, Box, Typography } from '@mui/material';
import { useCallback } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { policyService } from '../../../api/services/policyService';
import type { AttachmentDto, CaptureMode, GpsIn, ReadingKind } from '../../../api/types';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { AttachmentUpload } from '../../../components/meter/AttachmentUpload';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useSession } from '../../../session/useSession';
import { humanize } from '../../../utils/text';
import { photoExpected, readCapturePolicy } from './capturePolicy';
import { CapturePolicySummary } from './CapturePolicySummary';
import { GpsAttemptPanel } from './GpsAttemptPanel';
import { CAPTURE_MODE_OPTIONS, useMeterPhotoUpload } from './readingEvidenceKit';

interface PhotoAndGpsProps {
  photo: AttachmentDto | null;
  onPhotoChange: (photo: AttachmentDto | null) => void;
  photoRequired: boolean;
  gps: GpsIn | null;
  onRetryGps: () => void;
}

/** Meter photo upload and the GPS outcome of this browser. */
export function PhotoAndGps({
  photo,
  onPhotoChange,
  photoRequired,
  gps,
  onRetryGps,
}: PhotoAndGpsProps) {
  const upload = useMeterPhotoUpload();
  return (
    <>
      <AttachmentUpload
        label="Meter photo"
        value={photo}
        onChange={onPhotoChange}
        upload={upload}
        required={photoRequired}
        capture="environment"
        preview
        helperText="The original image is stored unchanged with its SHA-256 hash."
      />
      <Typography variant="subtitle2" component="h3">
        Location
      </Typography>
      <GpsAttemptPanel gps={gps} onRetry={onRetryGps} />
    </>
  );
}

interface CaptureEvidenceFieldsProps {
  /** Machine the reading is for (null until chosen); the effective policy is loaded for it. */
  machineId: string | null;
  siteId?: string | null;
  kind: ReadingKind;
  /** Current value of the Formik `capture_mode` field. */
  captureMode: CaptureMode | '';
  photo: AttachmentDto | null;
  onPhotoChange: (photo: AttachmentDto | null) => void;
  gps: GpsIn | null;
  onRetryGps: () => void;
}

/**
 * The effective METER_CAPTURE policy, capture mode + reading (Formik fields `capture_mode`,
 * `reading`), meter photo and GPS. Render inside a Formik form.
 */
export function CaptureEvidenceFields({
  machineId,
  siteId = null,
  kind,
  captureMode,
  photo,
  onPhotoChange,
  gps,
  onRetryGps,
}: CaptureEvidenceFieldsProps) {
  const { hasPermission } = useSession();
  // Capturing users may read the METER_CAPTURE policy they capture under (as the field apps do).
  const canReadPolicy = hasPermission(
    [PERMISSIONS.tenantPolicyRead, PERMISSIONS.tenantMeterCapture],
    'any',
  );
  const loadPolicy = useCallback(
    (signal: AbortSignal) =>
      policyService.effective(
        'METER_CAPTURE',
        { machine_id: machineId ?? undefined, site_id: siteId ?? undefined },
        signal,
      ),
    [machineId, siteId],
  );
  const policy = useAsyncResource(loadPolicy, [], canReadPolicy && machineId !== null);
  const view = policy.data === null ? null : readCapturePolicy(policy.data.values, kind);
  const kindLabel = humanize(kind).toLowerCase();
  return (
    <>
      {machineId !== null && (
        <CapturePolicySummary
          resource={canReadPolicy ? policy : null}
          view={view}
          kindLabel={kindLabel}
        />
      )}
      <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormikSelectField
          name="capture_mode"
          label="Capture mode"
          options={CAPTURE_MODE_OPTIONS}
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
      {view?.requiredMode != null && captureMode !== '' && captureMode !== view.requiredMode && (
        <Alert severity="warning">
          This differs from the policy ({humanize(view.requiredMode)}). The reading will be recorded
          and listed as an exception that requires review.
        </Alert>
      )}
      <PhotoAndGps
        photo={photo}
        onPhotoChange={onPhotoChange}
        photoRequired={photoExpected(view, captureMode)}
        gps={gps}
        onRetryGps={onRetryGps}
      />
    </>
  );
}
