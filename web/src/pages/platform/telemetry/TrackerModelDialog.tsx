import { Stack } from '@mui/material';
import { useState } from 'react';
import { withErrorCode } from '../../../api/lifecycle';
import { trackerModelService } from '../../../api/services/platformCatalogService';
import type { TrackerModelDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { CAPABILITY_LABELS } from '../../tenant/shared/display';
import { CapabilityChecklist } from './CapabilityChecklist';
import {
  ADAPTER_OPTIONS,
  CAPABILITY_FIELDS,
  EMPTY_MODEL,
  MODEL_ERROR_HINTS,
  MODEL_FIELDS,
  toModelCreate,
  toModelUpdate,
  trackerModelSchema,
  valuesFromModel,
  type TrackerModelValues,
} from './trackerModelForm';

interface TrackerModelDialogProps {
  /** Model to edit; omit to add one to the catalog. */
  model?: TrackerModelDto;
  onClose: () => void;
  onSaved: (model: TrackerModelDto) => void;
  onReload: () => void;
}

/** Add or edit an approved tracker model (adapter fixed after creation). Mount only while open. */
export function TrackerModelDialog({ model, onClose, onSaved, onReload }: TrackerModelDialogProps) {
  const [initialValues] = useState(() =>
    model === undefined ? EMPTY_MODEL : valuesFromModel(model),
  );
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  const editing = model !== undefined;

  const steps: FormStep<TrackerModelValues>[] = [
    {
      label: 'Model',
      fields: MODEL_FIELDS,
      render: () => (
        <>
          <FormikTextField name="manufacturer" label="Manufacturer" required />
          <FormikTextField name="model" label="Model" required />
          <FormikTextField name="protocol" label="Protocol" required />
          <FormikSelectField
            name="adapter"
            label="Adapter"
            options={ADAPTER_OPTIONS}
            disabled={editing}
            {...(editing ? { helperText: 'Fixed once created (trackers depend on it).' } : {})}
          />
        </>
      ),
    },
    {
      label: 'Capabilities',
      fields: CAPABILITY_FIELDS,
      render: () => (
        <>
          <CapabilityChecklist name="declared_capabilities" />
          <FormikTextField name="notes" label="Notes" multiline minRows={2} />
        </>
      ),
    },
  ];

  return (
    <StepperFormDialog<TrackerModelValues>
      open
      title={
        model === undefined ? 'Add tracker model' : `Edit ${model.manufacturer} ${model.model}`
      }
      steps={steps}
      initialValues={initialValues}
      validationSchema={trackerModelSchema}
      submitLabel={model === undefined ? 'Add model' : 'Save changes'}
      onClose={onClose}
      renderReview={(v) => (
        <Stack spacing={2}>
          {stale && (
            <StaleVersionAlert
              onReload={() => {
                onReload();
                onClose();
              }}
            />
          )}
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Manufacturer', value: v.manufacturer },
              { label: 'Model', value: v.model },
              { label: 'Protocol', value: v.protocol },
              { label: 'Adapter', value: v.adapter },
              {
                label: 'Declared capabilities',
                value: v.declared_capabilities.map((c) => CAPABILITY_LABELS[c]).join(', '),
              },
              { label: 'Notes', value: v.notes.trim() === '' ? '—' : v.notes },
            ]}
          />
        </Stack>
      )}
      onSubmit={async (v) => {
        try {
          if (model === undefined) {
            const body = toModelCreate(v);
            onSaved(await trackerModelService.create(body, keyFor(body)));
          } else {
            const body = toModelUpdate(v, model.version);
            onSaved(await guard(() => trackerModelService.update(model.id, body, keyFor(body))));
          }
        } catch (err) {
          throw withErrorCode(err, MODEL_ERROR_HINTS);
        }
      }}
    />
  );
}
