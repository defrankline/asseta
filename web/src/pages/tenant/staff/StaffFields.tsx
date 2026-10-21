import { Box } from '@mui/material';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { STAFF_KIND_OPTIONS, labelOf } from '../shared/display';
import type { StaffFormValues } from './staffForm';

export function PersonFields() {
  return (
    <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <FormikTextField name="full_name" label="Full name" required />
      <FormikSelectField name="kind" label="Kind" options={STAFF_KIND_OPTIONS} required />
      <FormikTextField name="employee_code" label="Employee code" />
      <FormikTextField name="phone" label="Phone" />
    </Box>
  );
}

export function LoginField() {
  return (
    <FormikTextField
      name="keycloak_subject"
      label="Login subject (optional)"
      helperText="Identity-provider user id, to link this person to an app login"
    />
  );
}

export function StaffReview({
  values: v,
  showActive,
}: {
  values: StaffFormValues;
  showActive: boolean;
}) {
  return (
    <KeyValueGrid
      items={[
        { label: 'Full name', value: v.full_name.trim() || '—' },
        { label: 'Kind', value: labelOf(STAFF_KIND_OPTIONS, v.kind) },
        { label: 'Employee code', value: v.employee_code.trim() || '—' },
        { label: 'Phone', value: v.phone.trim() || '—' },
        { label: 'Login', value: v.keycloak_subject.trim() === '' ? 'Not linked' : 'Linked' },
        ...(showActive ? [{ label: 'Active', value: v.is_active ? 'Yes' : 'No' }] : []),
      ]}
    />
  );
}
