import { Box, FormControlLabel, Switch } from '@mui/material';
import { useField } from 'formik';
import { useState } from 'react';
import { staffService } from '../../../api/services/staffService';
import type { StaffDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { STAFF_KIND_OPTIONS, labelOf } from '../shared/display';
import { staffSchema, toStaffPayload, type StaffFormValues } from './staffForm';

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
    {
      label: 'Person',
      fields: ['full_name', 'kind', 'employee_code', 'phone'],
      render: () => (
        <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormikTextField name="full_name" label="Full name" required />
          <FormikSelectField name="kind" label="Kind" options={STAFF_KIND_OPTIONS} required />
          <FormikTextField name="employee_code" label="Employee code" />
          <FormikTextField name="phone" label="Phone" />
        </Box>
      ),
    },
    {
      label: 'Access',
      fields: ['keycloak_subject', 'is_active'],
      render: () => (
        <>
          <FormikTextField
            name="keycloak_subject"
            label="Login subject (optional)"
            helperText="Identity-provider user id, to link this person to an app login"
          />
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
      renderReview={(v) => (
        <KeyValueGrid
          items={[
            { label: 'Full name', value: v.full_name.trim() || '—' },
            { label: 'Kind', value: labelOf(STAFF_KIND_OPTIONS, v.kind) },
            { label: 'Employee code', value: v.employee_code.trim() || '—' },
            { label: 'Phone', value: v.phone.trim() || '—' },
            { label: 'Login', value: v.keycloak_subject.trim() === '' ? 'Not linked' : 'Linked' },
            { label: 'Active', value: v.is_active ? 'Yes' : 'No' },
          ]}
        />
      )}
      onClose={onClose}
      onSubmit={async (values) => {
        const payload = toStaffPayload(values);
        onCreated(await staffService.create(payload, keyFor(payload)));
      }}
    />
  );
}
