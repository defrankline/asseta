import { Alert } from '@mui/material';
import { useField, useFormikContext } from 'formik';
import type { AttachmentDto } from '../../../api/types';
import { EvidenceUpload } from '../engineHours/allocations/EvidenceUpload';

/** Evidence upload bound to a Formik `AttachmentDto[]` field; each file uploads at once. */
export function FormikEvidenceField({
  name = 'evidence',
  label = 'Evidence',
  required = false,
  helperText,
}: {
  name?: string;
  label?: string;
  required?: boolean;
  helperText?: string;
}) {
  const [field, meta, helpers] = useField<AttachmentDto[]>(name);
  const { submitCount } = useFormikContext();
  return (
    <>
      <EvidenceUpload
        value={field.value}
        onChange={(next) => {
          void helpers.setValue(next);
        }}
        purpose="ADJUSTMENT_EVIDENCE"
        label={label}
        required={required}
        helperText={
          helperText ??
          (required
            ? 'Required by your company policy. Stored unchanged with its SHA-256 hash.'
            : 'Optional. Stored unchanged with its SHA-256 hash.')
        }
      />
      {(meta.touched || submitCount > 0) && typeof meta.error === 'string' && (
        <Alert severity="error">{meta.error}</Alert>
      )}
    </>
  );
}
