import { useState } from 'react';
import { machineService } from '../../../api/services/machineService';
import type { MachineDto } from '../../../api/types';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { InlineLookupDialogs } from './InlineLookupDialogs';
import {
  CLASSIFICATION_FIELDS,
  createMachineSchema,
  emptyMachineValues,
  IDENTITY_FIELDS,
  METERING_FIELDS,
  toCreatePayload,
  type MachineFormValues,
} from './machineForm';
import { ClassificationFields, IdentityFields, MeteringFields } from './MachineFormSteps';
import { MachineReview } from './MachineReview';
import { useMachineLookups } from './useMachineLookups';

interface CreateMachineDialogProps {
  onClose: () => void;
  onCreated: (machine: MachineDto) => void;
}

/** Identity → Classification → Metering & capacity → Review. Mount only while open. */
export function CreateMachineDialog({ onClose, onCreated }: CreateMachineDialogProps) {
  const [initialValues] = useState(emptyMachineValues);
  const keyFor = useIdempotencyKey();
  const lookups = useMachineLookups();

  const steps: FormStep<MachineFormValues>[] = [
    { label: 'Identity', fields: IDENTITY_FIELDS, render: () => <IdentityFields mode="create" /> },
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
        title="New machine"
        steps={steps}
        initialValues={initialValues}
        validationSchema={createMachineSchema}
        renderReview={(values) => <MachineReview values={values} lookups={lookups} mode="create" />}
        submitLabel="Create machine"
        onClose={onClose}
        onSubmit={async (values) => {
          const payload = toCreatePayload(values);
          const created = await machineService.create(payload, keyFor(payload));
          onCreated(created);
        }}
      />
      <InlineLookupDialogs lookups={lookups} />
    </>
  );
}
