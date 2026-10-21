import { useState } from 'react';
import { machineService } from '../../../api/services/machineService';
import type { AreaDto, CategoryDto } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { withErrorCode } from '../shared/errorHints';
import {
  areaSchema,
  categorySchema,
  LOOKUP_ERROR_HINTS,
  type AreaValues,
  type CategoryValues,
} from './lookupForms';
import type { RecordFormProps } from './MasterDataPanel';

/** Create or edit (PUT with `version`) a machine category. Mount only while open. */
export function CategoryFormDialog({
  record,
  onClose,
  onSaved,
  onReload,
}: RecordFormProps<CategoryDto>) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  const [initial] = useState<CategoryValues>({
    name: record?.name ?? '',
    description: record?.description ?? '',
  });
  return (
    <FormDialog<CategoryValues>
      open
      title={record === null ? 'New machine category' : `Edit ${record.name}`}
      initialValues={initial}
      validationSchema={categorySchema}
      submitLabel={record === null ? 'Create category' : 'Save changes'}
      onClose={onClose}
      onSubmit={async (v) => {
        const body = { name: v.name.trim(), description: v.description.trim() || null };
        try {
          const saved =
            record === null
              ? await machineService.createCategory(body, keyFor(body))
              : await guard(() => {
                  const put = { ...body, version: record.version };
                  return machineService.updateCategory(record.id, put, keyFor(put));
                });
          onSaved(saved);
        } catch (err) {
          throw withErrorCode(err, LOOKUP_ERROR_HINTS);
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
      <FormikTextField name="name" label="Name" required autoFocus />
      <FormikTextField name="description" label="Description" multiline minRows={2} />
    </FormDialog>
  );
}

/** Create or edit (PUT with `version`) an operating area. Mount only while open. */
export function AreaFormDialog({ record, onClose, onSaved, onReload }: RecordFormProps<AreaDto>) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  const [initial] = useState<AreaValues>({ code: record?.code ?? '', name: record?.name ?? '' });
  return (
    <FormDialog<AreaValues>
      open
      title={record === null ? 'New operating area' : `Edit ${record.code} · ${record.name}`}
      initialValues={initial}
      validationSchema={areaSchema}
      submitLabel={record === null ? 'Create area' : 'Save changes'}
      onClose={onClose}
      onSubmit={async (v) => {
        const body = { code: v.code.trim(), name: v.name.trim() };
        try {
          const saved =
            record === null
              ? await machineService.createArea(body, keyFor(body))
              : await guard(() => {
                  const put = { ...body, version: record.version };
                  return machineService.updateArea(record.id, put, keyFor(put));
                });
          onSaved(saved);
        } catch (err) {
          throw withErrorCode(err, LOOKUP_ERROR_HINTS);
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
      <FormikTextField name="code" label="Code" required autoFocus />
      <FormikTextField name="name" label="Name" required />
    </FormDialog>
  );
}
