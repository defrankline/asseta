import { Alert } from '@mui/material';
import { useState } from 'react';
import { object, string, type ObjectSchema } from 'yup';
import { newUuid } from '../../../api/ids';
import { meterService } from '../../../api/services/meterService';
import type {
  AttachmentDto,
  CaptureMode,
  CaptureResultDto,
  JobDto,
  MeterCaptureIn,
  ReadingKind,
} from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { humanize } from '../../../utils/text';
import { FormikFieldMachineIdPicker } from '../field/fieldPickers';
import { withErrorCode } from '../shared/errorHints';
import { JOB_ERROR_HINTS } from '../shared/jobDisplay';
import { CONSOLE_DEVICE_ID } from './capturePolicy';
import { CaptureEvidenceFields } from './ReadingEvidence';
import {
  captureModeField,
  gpsPendingError,
  readingField,
  useBrowserGps,
} from './readingEvidenceKit';

interface CaptureValues {
  machine_id: string;
  capture_mode: CaptureMode | '';
  reading: string;
}

const schemaFor = (needsMachine: boolean): ObjectSchema<CaptureValues> =>
  object({
    machine_id: needsMachine ? string().required('Choose the machine') : string().ensure(),
    capture_mode: captureModeField(),
    reading: readingField(),
  });

/** A machine the reading is for when it is not tied to a job (DAILY readings). */
export interface ReadingMachine {
  id: string;
  label: string;
}

interface ConsoleCaptureDialogProps {
  /** The job of an OPENING / CLOSING reading; omit for a DAILY reading (no job). */
  job?: JobDto;
  /** DAILY reading: the machine (omit to let the user choose one). Ignored when `job` is given. */
  machine?: ReadingMachine;
  kind: ReadingKind;
  /** `field`: a supervisor recording from a laptop or tablet (Field work), not an office fallback. */
  variant?: 'console' | 'field';
  onClose: () => void;
  onRecorded: (result: CaptureResultDto) => void;
}

/**
 * Records a meter reading from a browser: a job's opening / closing reading, or a DAILY reading of a
 * machine outside jobs (job optional). The capture `id` is generated once per dialog open so retries
 * never create a second reading, and the browser's real GPS outcome is submitted — coordinates are
 * never invented.
 */
export function ConsoleCaptureDialog({
  job,
  machine,
  kind,
  variant = 'console',
  onClose,
  onRecorded,
}: ConsoleCaptureDialogProps) {
  const [captureId] = useState(newUuid);
  const [capturedAt] = useState(() => new Date().toISOString());
  const keyFor = useIdempotencyKey();
  const { gps, retry } = useBrowserGps();
  const [photo, setPhoto] = useState<AttachmentDto | null>(null);
  const needsMachine = job === undefined && machine === undefined;
  const kindLabel = humanize(kind).toLowerCase();
  const target = job?.job_number ?? machine?.label ?? null;
  const title = `Record ${kindLabel} reading${target === null ? '' : ` · ${target}`}`;

  return (
    <FormDialog<CaptureValues>
      open
      title={title}
      initialValues={{ machine_id: '', capture_mode: '', reading: '' }}
      validationSchema={schemaFor(needsMachine)}
      submitLabel="Submit reading"
      maxWidth="md"
      onClose={onClose}
      onSubmit={async (v) => {
        if (gps === null) throw gpsPendingError();
        const machineId = machine?.id ?? v.machine_id;
        const payload: MeterCaptureIn = {
          id: captureId,
          ...(job !== undefined ? { job_id: job.id } : { job_id: null, machine_id: machineId }),
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
      {(formik) => {
        const machineId =
          job?.machine_id ??
          machine?.id ??
          (formik.values.machine_id === '' ? null : formik.values.machine_id);
        return (
          <>
            {variant === 'field' ? (
              <Alert severity="info">
                Photograph the hour meter (or choose a photo taken on site) and type the reading
                shown on it. The browser does not read the meter automatically, so an Automatic
                reading recorded here has no OCR result and is listed for review.
              </Alert>
            ) : (
              <Alert severity="info">
                Console fallback. Supervisors normally capture readings in the mobile app. The
                console does not run OCR, so an Automatic reading recorded here has no OCR result
                and will be listed for review.
              </Alert>
            )}
            {kind === 'DAILY' && (
              <Alert severity="info">
                A daily reading records the machine&apos;s engine hours outside a job, so hours
                between jobs are accounted for.
              </Alert>
            )}
            {needsMachine && (
              <FormikFieldMachineIdPicker name="machine_id" label="Machine" required />
            )}
            <CaptureEvidenceFields
              machineId={machineId}
              siteId={job?.job_site_id ?? null}
              kind={kind}
              captureMode={formik.values.capture_mode}
              photo={photo}
              onPhotoChange={setPhoto}
              gps={gps}
              onRetryGps={retry}
            />
          </>
        );
      }}
    </FormDialog>
  );
}
