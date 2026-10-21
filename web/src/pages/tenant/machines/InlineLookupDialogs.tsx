import { useState } from 'react';
import { machineService } from '../../../api/services/machineService';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useNotify } from '../../../notifications/useNotify';
import { areaSchema, categorySchema, type AreaValues, type CategoryValues } from './lookupForms';
import type { MachineLookups } from './useMachineLookups';

function NewCategoryDialog({ lookups }: { lookups: MachineLookups }) {
  const keyFor = useIdempotencyKey();
  const notify = useNotify();
  const [initial] = useState<CategoryValues>({ name: '', description: '' });
  return (
    <FormDialog<CategoryValues>
      open
      title="New machine category"
      initialValues={initial}
      validationSchema={categorySchema}
      submitLabel="Create category"
      onClose={lookups.closePending}
      onSubmit={async (v) => {
        const body = { name: v.name.trim(), description: v.description.trim() || null };
        const created = await machineService.createCategory(body, keyFor(body));
        lookups.categoryCreated(created);
        notify.success(`Category ${created.name} created.`);
      }}
    >
      <FormikTextField name="name" label="Name" required autoFocus />
      <FormikTextField name="description" label="Description" multiline minRows={2} />
    </FormDialog>
  );
}

function NewAreaDialog({ lookups }: { lookups: MachineLookups }) {
  const keyFor = useIdempotencyKey();
  const notify = useNotify();
  const [initial] = useState<AreaValues>({ code: '', name: '' });
  return (
    <FormDialog<AreaValues>
      open
      title="New operating area"
      initialValues={initial}
      validationSchema={areaSchema}
      submitLabel="Create area"
      onClose={lookups.closePending}
      onSubmit={async (v) => {
        const body = { code: v.code.trim(), name: v.name.trim() };
        const created = await machineService.createArea(body, keyFor(body));
        lookups.areaCreated(created);
        notify.success(`Operating area ${created.name} created.`);
      }}
    >
      <FormikTextField name="code" label="Code" required autoFocus />
      <FormikTextField name="name" label="Name" required />
    </FormDialog>
  );
}

/**
 * Inline create dialogs for categories / areas. Rendered as a sibling of the machine form (not
 * inside it) so the nested form's submit never bubbles into the machine form.
 */
export function InlineLookupDialogs({ lookups }: { lookups: MachineLookups }) {
  if (lookups.pending === null) return null;
  return lookups.pending.kind === 'category' ? (
    <NewCategoryDialog lookups={lookups} />
  ) : (
    <NewAreaDialog lookups={lookups} />
  );
}
