import { Alert, Typography } from '@mui/material';
import { object, string } from 'yup';
import { dataProtectionService } from '../../../api/services/dataProtectionService';
import type { TenantDto } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';

interface GoLiveDialogProps {
  tenant: TenantDto;
  onClose: () => void;
  onMarked: (tenant: TenantDto) => void;
}

/** The Platform Owner's explicit go-live: from then on the data reset tool refuses this tenant. */
export function GoLiveDialog({ tenant, onClose, onMarked }: GoLiveDialogProps) {
  const keyFor = useIdempotencyKey();
  const schema = object({
    confirm_name: string()
      .required('Type the company name')
      .test('match', 'The name does not match', (v) => v === tenant.display_name),
    note: string().ensure().max(500),
  });
  return (
    <FormDialog
      open
      title={`Mark ${tenant.display_name} as live`}
      initialValues={{ confirm_name: '', note: '' }}
      validationSchema={schema}
      submitLabel="Mark as live"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = { confirm_name: v.confirm_name, note: v.note.trim() || null };
        onMarked(await dataProtectionService.markLive(tenant.id, body, keyFor(body)));
      }}
    >
      <Alert severity="warning">
        A live company&apos;s data cannot be reset by the tenant data reset tool without a
        deliberate, recorded override.
      </Alert>
      <Typography variant="body2">
        Type <strong>{tenant.display_name}</strong> to confirm.
      </Typography>
      <FormikTextField name="confirm_name" label="Company name" required />
      <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
    </FormDialog>
  );
}
