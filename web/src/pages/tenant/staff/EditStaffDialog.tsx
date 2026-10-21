import { Stack } from '@mui/material';
import { useState } from 'react';
import { staffService } from '../../../api/services/staffService';
import type { StaffDto } from '../../../api/types';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { withErrorCode } from '../shared/errorHints';
import {
  STAFF_ERROR_HINTS,
  staffSchema,
  toStaffUpdatePayload,
  valuesFromStaff,
  type StaffFormValues,
  PERSON_FIELDS,
} from './staffForm';
import { LoginField, PersonFields, StaffReview } from './StaffFields';

interface EditStaffDialogProps {
  staff: StaffDto;
  onClose: () => void;
  onSaved: (staff: StaffDto) => void;
  /** STALE_VERSION: reload the record (the dialog closes). */
  onReload: () => void;
}

/** Person → Access → Review; saves with the `version` that was read. Mount only while open. */
export function EditStaffDialog({ staff, onClose, onSaved, onReload }: EditStaffDialogProps) {
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState(() => valuesFromStaff(staff));
  const { stale, guard } = useStaleVersion();
  const steps: FormStep<StaffFormValues>[] = [
    { label: 'Person', fields: PERSON_FIELDS, render: () => <PersonFields /> },
    { label: 'Access', fields: ['keycloak_subject'], render: () => <LoginField /> },
  ];
  return (
    <StepperFormDialog<StaffFormValues>
      open
      title={`Edit ${staff.full_name}`}
      steps={steps}
      initialValues={initialValues}
      validationSchema={staffSchema}
      submitLabel="Save changes"
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
          <StaffReview values={v} showActive={false} />
        </Stack>
      )}
      onClose={onClose}
      onSubmit={async (values) => {
        const payload = toStaffUpdatePayload(values, staff.version);
        try {
          onSaved(await guard(() => staffService.update(staff.id, payload, keyFor(payload))));
        } catch (err) {
          throw withErrorCode(err, STAFF_ERROR_HINTS);
        }
      }}
    />
  );
}
