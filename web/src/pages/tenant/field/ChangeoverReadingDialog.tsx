import { Alert } from '@mui/material';
import { useState } from 'react';
import { object, string, type ObjectSchema } from 'yup';
import { newUuid } from '../../../api/ids';
import { meterService } from '../../../api/services/meterService';
import type {
  AttachmentDto,
  CaptureMode,
  CaptureResultDto,
  FieldContractDto,
  JobDto,
  MeterCaptureIn,
} from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useEngineHoursRules } from '../engineHours/allocations/useEngineHoursPolicy';
import { ENGINE_HOURS_ERROR_HINTS } from '../engineHours/engineHoursDisplay';
import { CONSOLE_DEVICE_ID } from '../jobDetail/capturePolicy';
import { CaptureEvidenceFields } from '../jobDetail/ReadingEvidence';
import {
  captureModeField,
  gpsPendingError,
  readingField,
  useBrowserGps,
} from '../jobDetail/readingEvidenceKit';
import { withErrorCode } from '../shared/errorHints';
import { JOB_ERROR_HINTS } from '../shared/jobDisplay';
import {
  FormikFieldContractIdPicker,
  FormikFieldJobIdPicker,
  FormikRunningJobIdPicker,
} from './fieldPickers';

const HINTS = { ...JOB_ERROR_HINTS, ...ENGINE_HOURS_ERROR_HINTS };

interface ChangeoverValues {
  job_id: string;
  contract_id: string;
  next_job_id: string;
  capture_mode: CaptureMode | '';
  reading: string;
}

const schemaFor = (needsJob: boolean, nextJobRequired: boolean): ObjectSchema<ChangeoverValues> =>
  object({
    job_id: needsJob ? string().required('Choose the running job') : string().ensure(),
    contract_id: string().required('Choose the next customer'),
    next_job_id: nextJobRequired ? string().required('Choose the next job') : string().ensure(),
    capture_mode: captureModeField(),
    reading: readingField(),
  });

interface ChangeoverReadingDialogProps {
  /** The running job; omit to let the user choose one. */
  job?: JobDto;
  onClose: () => void;
  onRecorded: (result: CaptureResultDto) => void;
}

/**
 * A reading at which the machine moves to the next customer during a running job. The running job
 * stays the only one on the machine; from this reading on the hours are allocated to the next
 * customer. The reading `id` is fixed per dialog so retries never create a second reading.
 */
export function ChangeoverReadingDialog({
  job,
  onClose,
  onRecorded,
}: ChangeoverReadingDialogProps) {
  const [captureId] = useState(newUuid);
  const [capturedAt] = useState(() => new Date().toISOString());
  const keyFor = useIdempotencyKey();
  const { gps, retry } = useBrowserGps();
  const [photo, setPhoto] = useState<AttachmentDto | null>(null);
  const [picked, setPicked] = useState<JobDto | null>(null);
  const [contract, setContract] = useState<FieldContractDto | null>(null);
  const running = job ?? picked;
  const { changeoverJobRequired } = useEngineHoursRules(
    running?.machine_id ?? null,
    running?.job_site_id ?? null,
  );
  return (
    <FormDialog<ChangeoverValues>
      open
      title={`Record changeover reading${job === undefined ? '' : ` · ${job.job_number}`}`}
      initialValues={{
        job_id: '',
        contract_id: '',
        next_job_id: '',
        capture_mode: '',
        reading: '',
      }}
      validationSchema={schemaFor(job === undefined, changeoverJobRequired)}
      submitLabel="Submit reading"
      maxWidth="md"
      onClose={onClose}
      onSubmit={async (v) => {
        if (gps === null) throw gpsPendingError();
        if (running === null || contract === null) return;
        const payload: MeterCaptureIn = {
          id: captureId,
          job_id: running.id,
          kind: 'DAILY',
          capture_mode: v.capture_mode === '' ? 'MANUAL' : v.capture_mode,
          reading: v.reading.trim(),
          gps,
          device_id: CONSOLE_DEVICE_ID,
          captured_at: capturedAt,
          photo_attachment_id: photo?.id ?? null,
          ocr_value: null,
          ocr_confidence: null,
          changeover_to_customer_id: contract.customer_id,
          changeover_to_job_id: v.next_job_id === '' ? null : v.next_job_id,
        };
        try {
          onRecorded(await meterService.submitCapture(payload, keyFor(payload)));
        } catch (err) {
          throw withErrorCode(err, HINTS);
        }
      }}
    >
      {(formik) => (
        <>
          <Alert severity="info">
            Use this when the machine moves to another customer before this job is closed. The job
            keeps running; hours from this reading on are allocated to the next customer.
          </Alert>
          {job === undefined && (
            <FormikRunningJobIdPicker
              name="job_id"
              label="Running job"
              required
              onOptionChange={setPicked}
            />
          )}
          <FormikFieldContractIdPicker
            name="contract_id"
            label="Next customer"
            required
            onOptionChange={setContract}
          />
          <FormikFieldJobIdPicker
            name="next_job_id"
            label={changeoverJobRequired ? 'Next job' : 'Next job (optional)'}
            required={changeoverJobRequired}
            helperText={
              changeoverJobRequired
                ? 'Your company bills the hours after a changeover to this job.'
                : 'The job the machine moves on to, if it already exists.'
            }
          />
          <CaptureEvidenceFields
            machineId={running?.machine_id ?? null}
            siteId={running?.job_site_id ?? null}
            kind="DAILY"
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
