import { Alert, Box } from '@mui/material';
import { useState } from 'react';
import { object, string, type ObjectSchema } from 'yup';
import { meterService } from '../../../api/services/meterService';
import type { AttachmentDto, ResetDto, ResetIn } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikDateTimeField } from '../../../components/forms/FormikDateTimeField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { AttachmentUpload } from '../../../components/meter/AttachmentUpload';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../utils/time';
import { requiredDecimal, requiredInstant } from '../shared/formRules';

interface ResetValues {
  old_reading: string;
  new_reading: string;
  effective_at: string;
  reason: string;
}

const schema: ObjectSchema<ResetValues> = object({
  old_reading: requiredDecimal('Old reading'),
  new_reading: requiredDecimal('New reading'),
  effective_at: requiredInstant('Effective time'),
  reason: string()
    .trim()
    .required('Reason is required')
    .min(10, 'At least 10 characters')
    .max(2000, 'At most 2000 characters'),
});

interface RequestResetDialogProps {
  machineId: string;
  machineName: string;
  timeZone: string;
  onClose: () => void;
  onRequested: (reset: ResetDto) => void;
}

/** Readings → Reason & evidence → Review. A reset only takes effect once another person approves it. */
export function RequestResetDialog(props: RequestResetDialogProps) {
  const { machineId, machineName, timeZone, onClose, onRequested } = props;
  const keyFor = useIdempotencyKey();
  const uploadKey = useIdempotencyKey();
  const [evidence, setEvidence] = useState<AttachmentDto | null>(null);
  const [initialValues] = useState<ResetValues>(() => ({
    old_reading: '',
    new_reading: '',
    effective_at: new Date().toISOString(),
    reason: '',
  }));
  const upload = (file: File) =>
    meterService.upload(
      file,
      'RESET_EVIDENCE',
      uploadKey({ name: file.name, size: file.size, modified: file.lastModified }),
    );
  const steps: FormStep<ResetValues>[] = [
    {
      label: 'Readings',
      fields: ['old_reading', 'new_reading', 'effective_at'],
      render: () => (
        <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormikTextField
            name="old_reading"
            label="Old meter reading (before)"
            required
            slotProps={{ htmlInput: { inputMode: 'decimal' } }}
          />
          <FormikTextField
            name="new_reading"
            label="New meter reading (after)"
            required
            slotProps={{ htmlInput: { inputMode: 'decimal' } }}
          />
          <FormikDateTimeField
            name="effective_at"
            label="Effective time"
            timeZone={timeZone}
            required
          />
        </Box>
      ),
    },
    {
      label: 'Reason & evidence',
      fields: ['reason'],
      render: () => (
        <>
          <FormikTextField
            name="reason"
            label="Reason (meter replaced, rollover, repair…)"
            required
            multiline
            minRows={3}
          />
          <AttachmentUpload
            label="Supporting evidence (optional)"
            value={evidence}
            onChange={setEvidence}
            upload={upload}
            accept="image/*"
            helperText="e.g. a photo of the replaced meter or the workshop job card"
          />
        </>
      ),
    },
  ];
  return (
    <StepperFormDialog<ResetValues>
      open
      title={`Request meter reset · ${machineName}`}
      steps={steps}
      initialValues={initialValues}
      validationSchema={schema}
      submitLabel="Request reset"
      renderReview={(v) => (
        <>
          <Alert severity="info">
            The reset is pending until an approver other than you decides it (segregation of
            duties). Only approved resets re-base later readings.
          </Alert>
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Machine', value: machineName },
              { label: 'Old reading', value: v.old_reading.trim() },
              { label: 'New reading', value: v.new_reading.trim() },
              { label: 'Effective time', value: formatInstantIn(v.effective_at, timeZone) },
              { label: 'Reason', value: v.reason.trim() },
              {
                label: 'Evidence',
                value: evidence === null ? 'None' : `SHA-256 ${evidence.sha256.slice(0, 12)}…`,
              },
            ]}
          />
        </>
      )}
      onClose={onClose}
      onSubmit={async (v) => {
        const payload: ResetIn = {
          machine_id: machineId,
          old_reading: v.old_reading.trim(),
          new_reading: v.new_reading.trim(),
          effective_at: v.effective_at,
          reason: v.reason.trim(),
          evidence_attachment_id: evidence?.id ?? null,
        };
        onRequested(await meterService.requestReset(payload, keyFor(payload)));
      }}
    />
  );
}
