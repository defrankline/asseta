import { FormControlLabel, Switch } from '@mui/material';
import { useField } from 'formik';
import { useState } from 'react';
import { staffService } from '../../../api/services/staffService';
import type { StaffDto } from '../../../api/types';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { PERSON_FIELDS, staffSchema, toStaffPayload, type StaffFormValues } from './staffForm';
import { LoginField, PersonFields, StaffReview } from './StaffFields';

function ActiveSwitch() {
  const [field, , helpers] = useField<boolean>('is_active');
  return (
    <FormControlLabel
      control={
        <Switch
          checked={field.value}
          onChange={(e) => {
            void helpers.setValue(e.target.checked);
          }}
        />
      }
      label="Active"
    />
  );
}

interface CreateStaffDialogProps {
  onClose: () => void;
  onCreated: (staff: StaffDto) => void;
}

/** Person → Access → Review. Mount only while open. */
export function CreateStaffDialog({ onClose, onCreated }: CreateStaffDialogProps) {
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState<StaffFormValues>({
    full_name: '',
    kind: 'OPERATOR',
    employee_code: '',
    phone: '',
    keycloak_subject: '',
    is_active: true,
  });
  const steps: FormStep<StaffFormValues>[] = [
    { label: 'Person', fields: PERSON_FIELDS, render: () => <PersonFields /> },
    {
      label: 'Access',
      fields: ['keycloak_subject', 'is_active'],
      render: () => (
        <>
          <LoginField />
          <ActiveSwitch />
        </>
      ),
    },
  ];
  return (
    <StepperFormDialog<StaffFormValues>
      open
      title="New staff member"
      steps={steps}
      initialValues={initialValues}
      validationSchema={staffSchema}
      submitLabel="Create staff member"
      renderReview={(v) => <StaffReview values={v} showActive />}
      onClose={onClose}
      onSubmit={async (values) => {
        const payload = toStaffPayload(values);
        onCreated(await staffService.create(payload, keyFor(payload)));
      }}
    />
  );
}
