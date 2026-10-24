import { Alert } from '@mui/material';
import { useState } from 'react';
import { object, string, type ObjectSchema } from 'yup';
import { newUuid } from '../../../api/ids';
import { engineHoursService } from '../../../api/services/engineHoursService';
import type {
  AttachmentDto,
  CaptureMode,
  CorrectionDto,
  CorrectionIn,
  MeterCaptureDto,
  MeterCaptureIn,
} from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import { CONSOLE_DEVICE_ID } from '../jobDetail/capturePolicy';
import { CaptureEvidenceFields } from '../jobDetail/ReadingEvidence';
import {
  captureModeField,
  gpsPendingError,
  readingField,
  useBrowserGps,
} from '../jobDetail/readingEvidenceKit';
import { withErrorCode } from '../shared/errorHints';
import { ENGINE_HOURS_ERROR_HINTS } from './engineHoursDisplay';

/** The server needs a correction reason of at least 10 characters. */
export const CORRECTION_REASON_MIN = 10;

interface CorrectionValues {
  reason: string;
  capture_mode: CaptureMode | '';
  reading: string;
}

const schema: ObjectSchema<CorrectionValues> = object({
  reason: string()
    .trim()
    .required('A reason is required')
    .min(CORRECTION_REASON_MIN, `At least ${String(CORRECTION_REASON_MIN)} characters`)
    .max(2000, 'At most 2000 characters'),
  capture_mode: captureModeField(),
  reading: readingField(),
});

interface ProposeCorrectionDialogProps {
  /** The live reading to supersede. */
  capture: MeterCaptureDto;
  /** e.g. "EX-01 · Excavator" (shown in the summary). */
  machineLabel: string;
  onClose: () => void;
  onProposed: (c: CorrectionDto) => void;
}

/**
 * Propose superseding a reading with a corrected value and its own evidence (same kind, job and
 * machine; the original capture time is kept). Applied when a second person approves it, unless the
 * tenant's policy lets an approver correct directly. The replacement id is fixed per dialog.
 */
export function ProposeCorrectionDialog({
  capture,
  machineLabel,
  onClose,
  onProposed,
}: ProposeCorrectionDialogProps) {
  const [replacementId] = useState(newUuid);
  const keyFor = useIdempotencyKey();
  const timeZone = useDisplayTimeZone();
  const { gps, retry } = useBrowserGps();
  const [photo, setPhoto] = useState<AttachmentDto | null>(null);
  return (
    <FormDialog<CorrectionValues>
      open
      title={`Propose a correction · ${humanize(capture.kind).toLowerCase()} reading ${capture.reading} h`}
      initialValues={{ reason: '', capture_mode: '', reading: '' }}
      validationSchema={schema}
      submitLabel="Propose correction"
      maxWidth="md"
      onClose={onClose}
      onSubmit={async (v) => {
        if (gps === null) throw gpsPendingError();
        const replacement: MeterCaptureIn = {
          id: replacementId,
          job_id: capture.job_id,
          machine_id: capture.machine_id,
          kind: capture.kind,
          capture_mode: v.capture_mode === '' ? 'MANUAL' : v.capture_mode,
          reading: v.reading.trim(),
          gps,
          device_id: CONSOLE_DEVICE_ID,
          captured_at: capture.captured_at,
          photo_attachment_id: photo?.id ?? null,
          ocr_value: null,
          ocr_confidence: null,
        };
        const body: CorrectionIn = {
          superseded_capture_id: capture.id,
          reason: v.reason.trim(),
          replacement,
        };
        try {
          onProposed(await engineHoursService.proposeCorrection(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, ENGINE_HOURS_ERROR_HINTS);
        }
      }}
    >
      {(formik) => (
        <>
          <KeyValueGrid
            columns={3}
            items={[
              { label: 'Machine', value: machineLabel },
              { label: 'Reading being corrected', value: `${capture.reading} h` },
              { label: 'Captured', value: formatInstantIn(capture.captured_at, timeZone) },
            ]}
          />
          <Alert severity="info">
            The original reading stays on record. The corrected value replaces it once a second
            person approves (the person proposing cannot approve their own correction).
          </Alert>
          <FormikTextField
            name="reason"
            label="Reason for the correction"
            required
            multiline
            minRows={2}
            helperText="At least 10 characters; kept on the record for audit."
          />
          <CaptureEvidenceFields
            machineId={capture.machine_id}
            kind={capture.kind}
            captureMode={formik.values.capture_mode}
            photo={photo}
            onPhotoChange={setPhoto}
            gps={gps}
            onRetryGps={retry}
          />
        </>
      )}
    </FormDialog>
  );
}
