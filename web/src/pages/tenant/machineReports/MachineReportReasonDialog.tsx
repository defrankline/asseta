import { object, string, type ObjectSchema } from 'yup';
import { withErrorCode } from '../../../api/lifecycle';
import type { MachineReportReasonDto } from '../../../api/machineReportTypes';
import { machineReportReasonService } from '../../../api/services/machineReportService';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { REASON_ERROR_HINTS } from './machineReportDisplay';

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

interface MachineReportReasonDialogProps {
  /** Reason to edit; omit to add one. */
  reason?: MachineReportReasonDto;
  onClose: () => void;
  onSaved: (reason: MachineReportReasonDto) => void;
  onReload: () => void;
}

/** Add or edit a reason for non-productive hours on machine reports. Mount while open. */
export function MachineReportReasonDialog({
  reason,
  onClose,
  onSaved,
  onReload,
}: MachineReportReasonDialogProps) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  return (
    <FormDialog<ReasonValues>
      open
      title={reason === undefined ? 'New reason' : `Edit ${reason.name}`}
      initialValues={{
        code: reason?.code ?? '',
        name: reason?.name ?? '',
        description: reason?.description ?? '',
      }}
      validationSchema={schema}
      submitLabel={reason === undefined ? 'Add reason' : 'Save changes'}
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
            onSaved(await machineReportReasonService.create(fields, keyFor(fields)));
          } else {
            const body = { ...fields, version: reason.version };
            onSaved(
              await guard(() => machineReportReasonService.update(reason.id, body, keyFor(body))),
            );
          }
        } catch (err) {
          throw withErrorCode(err, REASON_ERROR_HINTS);
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
      <FormikTextField
        name="code"
        label="Code"
        required
        helperText="Short and stable, e.g. TRANSIT"
      />
      <FormikTextField name="name" label="Name" required helperText="What supervisors pick" />
      <FormikTextField name="description" label="Description" multiline minRows={2} />
    </FormDialog>
  );
}
