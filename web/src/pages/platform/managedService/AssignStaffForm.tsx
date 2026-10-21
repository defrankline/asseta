import { Alert, Box, Button, Stack } from '@mui/material';
import { Form, Formik } from 'formik';
import { useCallback, useMemo } from 'react';
import { object, string } from 'yup';
import { mandateService } from '../../../api/services/mandateService';
import type { MandateAssignmentIn, MandateDetailDto } from '../../../api/types';
import { FormikSelectField, type SelectOption } from '../../../components/forms/FormikSelectField';
import { applySubmitError, statusMessage } from '../../../components/forms/submitHandling';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';

const schema = object({
  user_id: string().required('Platform staff is required'),
  role_key: string().required('Client role is required'),
});

interface AssignStaffFormProps {
  mandateId: string;
  onAssigned: (mandate: MandateDetailDto) => void;
}

/** Give a platform staff member a client role under the mandate (roles filtered by scope). */
export function AssignStaffForm({ mandateId, onAssigned }: AssignStaffFormProps) {
  const keyFor = useIdempotencyKey();
  const loadStaff = useCallback((signal: AbortSignal) => mandateService.listStaff(signal), []);
  const loadRoles = useCallback(
    (signal: AbortSignal) => mandateService.listRoles(mandateId, signal),
    [mandateId],
  );
  const staff = useAsyncResource(loadStaff);
  const roles = useAsyncResource(loadRoles);
  const staffOptions = useMemo<SelectOption[]>(
    () =>
      (staff.data ?? []).map((s) => ({
        value: s.user_id,
        label: `${s.display_name} (${s.email})`,
      })),
    [staff.data],
  );
  const roleOptions = useMemo<SelectOption[]>(
    () => (roles.data ?? []).map((r) => ({ value: r.key, label: r.key })),
    [roles.data],
  );
  const loadError = staff.error ?? roles.error;

  return (
    <Formik<MandateAssignmentIn>
      initialValues={{ user_id: '', role_key: '' }}
      validationSchema={schema}
      onSubmit={async (v, helpers) => {
        helpers.setStatus(undefined);
        try {
          onAssigned(await mandateService.assign(mandateId, v, keyFor(v)));
          helpers.resetForm();
        } catch (err) {
          applySubmitError(err, helpers);
        }
      }}
    >
      {(formik) => (
        <Form noValidate aria-label="Assign staff">
          <Stack spacing={2}>
            {loadError !== null && (
              <Alert severity="error">Could not load staff or roles: {loadError.message}</Alert>
            )}
            {statusMessage(formik.status) !== null && (
              <Alert severity="error">{statusMessage(formik.status)}</Alert>
            )}
            <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormikSelectField
                name="user_id"
                label="Platform staff"
                options={staffOptions}
                required
                disabled={staff.loading}
              />
              <FormikSelectField
                name="role_key"
                label="Client role"
                options={roleOptions}
                required
                disabled={roles.loading}
              />
            </Box>
            <div>
              <Button type="submit" variant="outlined" loading={formik.isSubmitting}>
                Assign
              </Button>
            </div>
          </Stack>
        </Form>
      )}
    </Formik>
  );
}
