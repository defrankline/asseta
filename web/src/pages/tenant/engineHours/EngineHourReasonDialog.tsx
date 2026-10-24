import { mixed, object, string, type ObjectSchema } from 'yup';
import { withErrorCode } from '../../../api/lifecycle';
import { engineHoursService } from '../../../api/services/engineHoursService';
import type { EngineHourReasonDto, EngineHourReasonKind } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { ENGINE_HOURS_ERROR_HINTS, REASON_KIND_OPTIONS } from './engineHoursDisplay';

interface ReasonValues {
  kind: EngineHourReasonKind | '';
  code: string;
  name: string;
  description: string;
}

const schema: ObjectSchema<ReasonValues> = object({
  kind: mixed<EngineHourReasonKind | ''>()
    .oneOf(['NON_CUSTOMER_CATEGORY', 'VARIANCE_REASON'], 'Choose the list')
    .required('Choose the list'),
  code: string().trim().required('Code is required').max(32, 'At most 32 characters'),
  name: string().trim().required('Name is required').max(120, 'At most 120 characters'),
  description: string().trim().ensure().max(1000, 'At most 1000 characters'),
});

interface EngineHourReasonDialogProps {
  /** Entry to edit; omit to create (optionally in a preselected list). */
  reason?: EngineHourReasonDto;
  defaultKind?: EngineHourReasonKind;
  onClose: () => void;
  onSaved: (reason: EngineHourReasonDto) => void;
  onReload: () => void;
}

/** Create or edit an engine-hour list entry (the list kind is fixed once created). Mount while open. */
export function EngineHourReasonDialog({
  reason,
  defaultKind,
  onClose,
  onSaved,
  onReload,
}: EngineHourReasonDialogProps) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  return (
    <FormDialog<ReasonValues>
      open
      title={reason === undefined ? 'New list entry' : `Edit ${reason.name}`}
      initialValues={{
        kind: reason?.kind ?? defaultKind ?? '',
        code: reason?.code ?? '',
        name: reason?.name ?? '',
        description: reason?.description ?? '',
      }}
      validationSchema={schema}
      submitLabel={reason === undefined ? 'Create entry' : 'Save changes'}
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
            const body = {
              ...fields,
              kind: v.kind === 'VARIANCE_REASON' ? 'VARIANCE_REASON' : 'NON_CUSTOMER_CATEGORY',
            } as const;
            onSaved(await engineHoursService.createReason(body, keyFor(body)));
          } else {
            const body = { ...fields, version: reason.version };
            onSaved(
              await guard(() => engineHoursService.updateReason(reason.id, body, keyFor(body))),
            );
          }
        } catch (err) {
          throw withErrorCode(err, ENGINE_HOURS_ERROR_HINTS);
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
      <FormikSelectField
        name="kind"
        label="List"
        options={REASON_KIND_OPTIONS}
        required
        disabled={reason !== undefined}
      />
      <FormikTextField name="code" label="Code" required />
      <FormikTextField name="name" label="Name" required />
      <FormikTextField name="description" label="Description" multiline minRows={2} />
    </FormDialog>
  );
}
