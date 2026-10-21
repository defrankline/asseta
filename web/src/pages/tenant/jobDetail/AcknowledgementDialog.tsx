import { Box, Typography } from '@mui/material';
import { useState } from 'react';
import { mixed, object, string, type ObjectSchema } from 'yup';
import { newUuid } from '../../../api/ids';
import { jobService } from '../../../api/services/jobService';
import { meterService } from '../../../api/services/meterService';
import type {
  AcknowledgementDto,
  AcknowledgementIn,
  AcknowledgementMethod,
  AttachmentDto,
  JobDto,
} from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikDateTimeField } from '../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { AttachmentUpload } from '../../../components/meter/AttachmentUpload';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../utils/time';
import { labelOf } from '../shared/display';
import { withErrorCode } from '../shared/errorHints';
import { optionalDecimal, optionalText, orNull, requiredInstant } from '../shared/formRules';
import { ACK_METHOD_OPTIONS, JOB_ERROR_HINTS } from '../shared/jobDisplay';

interface AckValues {
  method: AcknowledgementMethod;
  signer_name: string;
  signer_phone: string;
  acknowledged_hours: string;
  captured_at: string;
  signature: AttachmentDto | null;
}

const schema: ObjectSchema<AckValues> = object({
  method: mixed<AcknowledgementMethod>()
    .oneOf(['SIGNATURE', 'NAME_CONFIRMATION'])
    .required('Choose a method'),
  signer_name: string()
    .trim()
    .required('Signer name is required')
    .max(200, 'At most 200 characters'),
  signer_phone: optionalText('Signer phone', 40),
  acknowledged_hours: optionalDecimal('Acknowledged hours'),
  captured_at: requiredInstant('Acknowledged at'),
  signature: mixed<AttachmentDto>()
    .nullable()
    .defined()
    .test('signature', 'Upload the signature image', function (v) {
      return (this.parent as AckValues).method !== 'SIGNATURE' || v !== null;
    }),
});

interface AcknowledgementDialogProps {
  job: JobDto;
  /** Prefill for acknowledged hours (the job's billable hours when known). */
  suggestedHours: string | null;
  timeZone: string;
  onClose: () => void;
  onRecorded: (ack: AcknowledgementDto) => void;
}

/** Customer → Hours & evidence → Review. `client_id` is fixed per open (retry-safe). */
export function AcknowledgementDialog(props: AcknowledgementDialogProps) {
  const { job, timeZone, onClose, onRecorded } = props;
  const keyFor = useIdempotencyKey();
  const uploadKey = useIdempotencyKey();
  const [clientId] = useState(newUuid);
  const [initialValues] = useState<AckValues>(() => ({
    method: 'NAME_CONFIRMATION',
    signer_name: '',
    signer_phone: '',
    acknowledged_hours: props.suggestedHours ?? '',
    captured_at: new Date().toISOString(),
    signature: null,
  }));
  const upload = (file: File) =>
    meterService.upload(
      file,
      'SIGNATURE',
      uploadKey({ name: file.name, size: file.size, modified: file.lastModified }),
    );
  const steps: FormStep<AckValues>[] = [
    {
      label: 'Customer',
      fields: ['method', 'signer_name', 'signer_phone'],
      render: () => (
        <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormikSelectField name="method" label="Method" options={ACK_METHOD_OPTIONS} required />
          <FormikTextField name="signer_name" label="Customer representative" required />
          <FormikTextField name="signer_phone" label="Phone" />
        </Box>
      ),
    },
    {
      label: 'Hours & evidence',
      fields: ['acknowledged_hours', 'captured_at', 'signature'],
      render: (formik) => (
        <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormikTextField
            name="acknowledged_hours"
            label="Acknowledged hours"
            helperText="Hours the customer confirms (optional)"
            slotProps={{ htmlInput: { inputMode: 'decimal' } }}
          />
          <FormikDateTimeField
            name="captured_at"
            label="Acknowledged at"
            timeZone={timeZone}
            required
          />
          {formik.values.method === 'SIGNATURE' && (
            <Box className="sm:col-span-2">
              <AttachmentUpload
                label="Signature image"
                required
                value={formik.values.signature}
                onChange={(a) => {
                  void formik.setFieldValue('signature', a);
                }}
                upload={upload}
              />
              {typeof formik.errors.signature === 'string' && formik.touched.signature === true && (
                <Typography variant="caption" color="error">
                  {formik.errors.signature}
                </Typography>
              )}
            </Box>
          )}
        </Box>
      ),
    },
  ];
  return (
    <StepperFormDialog<AckValues>
      open
      title={`Customer acknowledgement · ${job.job_number}`}
      steps={steps}
      initialValues={initialValues}
      validationSchema={schema}
      submitLabel="Record acknowledgement"
      renderReview={(v) => (
        <KeyValueGrid
          columns={2}
          items={[
            { label: 'Method', value: labelOf(ACK_METHOD_OPTIONS, v.method) },
            { label: 'Customer representative', value: v.signer_name.trim() },
            { label: 'Phone', value: v.signer_phone.trim() || '—' },
            {
              label: 'Acknowledged hours',
              value: v.acknowledged_hours.trim() === '' ? '—' : `${v.acknowledged_hours.trim()} h`,
            },
            { label: 'Acknowledged at', value: formatInstantIn(v.captured_at, timeZone) },
            {
              label: 'Signature',
              value: v.signature === null ? '—' : `SHA-256 ${v.signature.sha256.slice(0, 12)}…`,
            },
          ]}
        />
      )}
      onClose={onClose}
      onSubmit={async (v) => {
        const signature = v.method === 'SIGNATURE' ? v.signature : null;
        const payload: AcknowledgementIn = {
          client_id: clientId,
          method: v.method,
          signer_name: v.signer_name.trim(),
          signer_phone: orNull(v.signer_phone),
          acknowledged_hours: orNull(v.acknowledged_hours),
          captured_at: v.captured_at,
          signature_attachment_id: signature?.id ?? null,
        };
        try {
          onRecorded(await jobService.acknowledge(job.id, payload, keyFor(payload)));
        } catch (err) {
          throw withErrorCode(err, JOB_ERROR_HINTS);
        }
      }}
    />
  );
}
