import { Alert, Box, Button, Stack } from '@mui/material';
import { Form, Formik } from 'formik';
import { useMemo } from 'react';
import { object, string } from 'yup';
import { mandateService } from '../../../api/services/mandateService';
import type {
  AssignableRoleDto,
  MandateAssignmentIn,
  MandateDetailDto,
  PlatformStaffDto,
} from '../../../api/types';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { applySubmitError, statusMessage } from '../../../components/forms/submitHandling';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import {
  roleKey,
  roleSearch,
  searchPlatformStaff,
  staffId,
  staffLabel,
} from '../shared/platformLookups';

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
  const searchRoles = useMemo(() => roleSearch(mandateId), [mandateId]);

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
            {statusMessage(formik.status) !== null && (
              <Alert severity="error">{statusMessage(formik.status)}</Alert>
            )}
            <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormikAsyncIdAutocomplete<PlatformStaffDto>
                name="user_id"
                label="Platform staff"
                required
                fetchOptions={searchPlatformStaff}
                getOptionId={staffId}
                getOptionLabel={staffLabel}
              />
              <FormikAsyncIdAutocomplete<AssignableRoleDto>
                name="role_key"
                label="Client role"
                required
                helperText="Roles allowed by the mandate scope"
                fetchOptions={searchRoles}
                getOptionId={roleKey}
                getOptionLabel={roleKey}
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
