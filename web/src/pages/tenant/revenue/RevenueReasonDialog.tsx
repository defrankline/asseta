import { object, string, type ObjectSchema } from 'yup';
import { withErrorCode } from '../../../api/lifecycle';
import { revenueService } from '../../../api/services/revenueService';
import type { RevenueReasonDto } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { REVENUE_ERROR_HINTS } from './revenueDisplay';

interface ReasonValues {
  code: string;
  name: string;
  description: string;
}

const schema: ObjectSchema<ReasonValues> = object({
  code: string().trim().required('Code is required').max(32, 'At most 32 characters'),
  name: string().trim().required('Name is required').max(120, 'At most 120 characters'),
  description: string().trim().ensure().max(1000, 'At most 1000 characters'),
});

interface RevenueReasonDialogProps {
  /** Reason to edit; omit to create. */
  reason?: RevenueReasonDto;
  onClose: () => void;
  onSaved: (reason: RevenueReasonDto) => void;
  onReload: () => void;
}

/** Create or edit an entry of the revenue reason list. Mount while open. */
export function RevenueReasonDialog({
  reason,
  onClose,
  onSaved,
  onReload,
}: RevenueReasonDialogProps) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  return (
    <FormDialog<ReasonValues>
      open
      title={reason === undefined ? 'New revenue reason' : `Edit ${reason.name}`}
      initialValues={{
        code: reason?.code ?? '',
        name: reason?.name ?? '',
        description: reason?.description ?? '',
      }}
      validationSchema={schema}
      submitLabel={reason === undefined ? 'Create reason' : 'Save changes'}
      onClose={onClose}
      onSubmit={async (v) => {
        const description = v.description.trim();
        const fields = {
          code: v.code.trim(),
          name: v.name.trim(),
          description: description === '' ? null : description,
        };
        try {
          if (reason === undefined) {
            onSaved(await revenueService.createReason(fields, keyFor(fields)));
          } else {
            const body = { ...fields, version: reason.version };
            onSaved(await guard(() => revenueService.updateReason(reason.id, body, keyFor(body))));
          }
        } catch (err) {
          throw withErrorCode(err, REVENUE_ERROR_HINTS);
        }
      }}
    >
      {stale && (
        <StaleVersionAlert
          onReload={() => {
            onReload();
            onClose();
          }}
        />
      )}
      <FormikTextField name="code" label="Code" required />
      <FormikTextField name="name" label="Name" required />
      <FormikTextField name="description" label="Description" multiline minRows={2} />
    </FormDialog>
  );
}
