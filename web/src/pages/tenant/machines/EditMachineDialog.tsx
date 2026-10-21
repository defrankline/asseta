import { Alert, Button, Stack } from '@mui/material';
import { useState } from 'react';
import { ApiError } from '../../../api/ApiError';
import { machineService } from '../../../api/services/machineService';
import type { MachineDto } from '../../../api/types';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { InlineLookupDialogs } from './InlineLookupDialogs';
import {
  CLASSIFICATION_FIELDS,
  EDIT_IDENTITY_FIELDS,
  editMachineSchema,
  METERING_FIELDS,
  toUpdatePayload,
  valuesFromMachine,
  type MachineFormValues,
} from './machineForm';
import { ClassificationFields, IdentityFields, MeteringFields } from './MachineFormSteps';
import { MachineReview } from './MachineReview';
import { useMachineLookups } from './useMachineLookups';

export interface EditMachineDialogProps {
  machine: MachineDto;
  onClose: () => void;
  /** Called with the saved machine (new `version`). */
  onSaved: (machine: MachineDto) => void;
  /** Called when the server reports STALE_VERSION and the user chooses to reload. */
  onReloadRequested: () => void;
}

export const STALE_VERSION_MESSAGE =
  'This machine was changed by someone else. Reload to see the latest version.';

/**
 * Edit a machine with optimistic concurrency: the PUT carries the `version` that was read. On
 * STALE_VERSION nothing is overwritten; the user is asked to reload. Mount only while open.
 */
export function EditMachineDialog({
  machine,
  onClose,
  onSaved,
  onReloadRequested,
}: EditMachineDialogProps) {
  const [initialValues] = useState(() => valuesFromMachine(machine));
  const [stale, setStale] = useState(false);
  const keyFor = useIdempotencyKey();
  const lookups = useMachineLookups();

  const steps: FormStep<MachineFormValues>[] = [
    {
      label: 'Identity & status',
      fields: EDIT_IDENTITY_FIELDS,
      render: () => <IdentityFields mode="edit" />,
    },
    {
      label: 'Classification',
      fields: CLASSIFICATION_FIELDS,
      render: (formik) => (
        <ClassificationFields formik={formik} lookups={lookups} canCreateLookups />
      ),
    },
    { label: 'Metering & capacity', fields: METERING_FIELDS, render: () => <MeteringFields /> },
  ];

  return (
    <>
      <StepperFormDialog<MachineFormValues>
        open
        title={`Edit ${machine.asset_code}`}
        steps={steps}
        initialValues={initialValues}
        validationSchema={editMachineSchema}
        renderReview={(values) => (
          <Stack spacing={2}>
            {stale && (
              <Alert
                severity="warning"
                action={
                  <Button
                    color="inherit"
                    size="small"
                    onClick={() => {
                      onReloadRequested();
                      onClose();
                    }}
                  >
                    Reload
                  </Button>
                }
              >
                {STALE_VERSION_MESSAGE}
              </Alert>
            )}
            <MachineReview values={values} lookups={lookups} mode="edit" />
          </Stack>
        )}
        submitLabel="Save changes"
        onClose={onClose}
        onSubmit={async (values) => {
          const payload = toUpdatePayload(values, machine.version);
          try {
            const saved = await machineService.update(machine.id, payload, keyFor(payload));
            onSaved(saved);
          } catch (err) {
            if (err instanceof ApiError && err.code === 'STALE_VERSION') setStale(true);
            throw err;
          }
        }}
      />
      <InlineLookupDialogs lookups={lookups} />
    </>
  );
}
