import { mixed, object } from 'yup';
import { tenantService } from '../../../api/services/tenantService';
import type { TenantDto, VerificationIn, VerificationStatus } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { reasonField } from '../shared/validators';

const schema = object({
  status: mixed<VerificationStatus>()
    .oneOf(['UNVERIFIED', 'VERIFIED', 'REJECTED'])
    .required('Status is required'),
  note: reasonField('Note'),
});

const INITIAL: { status: VerificationStatus; note: string } = { status: 'VERIFIED', note: '' };

const OPTIONS = [
  { value: 'VERIFIED', label: 'Verified' },
  { value: 'REJECTED', label: 'Rejected' },
  { value: 'UNVERIFIED', label: 'Unverified' },
];

interface VerifyTenantDialogProps {
  tenant: TenantDto;
  onClose: () => void;
  onVerified: (tenant: TenantDto) => void;
}

/** Record the company-record verification decision (required before activation). */
export function VerifyTenantDialog({ tenant, onClose, onVerified }: VerifyTenantDialogProps) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog
      open
      title={`Verify ${tenant.display_name}`}
      initialValues={INITIAL}
      validationSchema={schema}
      submitLabel="Save verification"
      onClose={onClose}
      onSubmit={async (v) => {
        const body: VerificationIn = { status: v.status, note: v.note.trim() };
        onVerified(await tenantService.verify(tenant.id, body, keyFor(body)));
      }}
    >
      <FormikSelectField name="status" label="Verification status" options={OPTIONS} required />
      <FormikTextField
        name="note"
        label="Note"
        required
        multiline
        minRows={2}
        helperText="What was checked (registration certificate, TIN, ...)"
      />
    </FormDialog>
  );
}
