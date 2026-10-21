import { useCallback, useState } from 'react';
import { object, string, type ObjectSchema } from 'yup';
import { machineService } from '../../../api/services/machineService';
import { staffService } from '../../../api/services/staffService';
import type { AssignIn, AssignmentDto, AssignmentRole, StaffDto } from '../../../api/types';
import { AsyncAutocomplete } from '../../../components/data/AsyncAutocomplete';
import { DateTimeField } from '../../../components/forms/DateTimeField';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';

interface AssignValues {
  staff_member_id: string;
  role: string;
  effective_from: string;
}

const ROLE_OPTIONS: { value: AssignmentRole; label: string }[] = [
  { value: 'SUPERVISOR', label: 'Supervisor' },
  { value: 'OPERATOR', label: 'Operator' },
];

const schema: ObjectSchema<AssignValues> = object({
  staff_member_id: string().required('Choose a staff member'),
  role: string().oneOf(['SUPERVISOR', 'OPERATOR'], 'Choose a role').required('Choose a role'),
  effective_from: string().required('Effective from is required'),
});

interface AssignStaffDialogProps {
  machineId: string;
  timeZone: string;
  onClose: () => void;
  onAssigned: (assignment: AssignmentDto) => void;
}

/** Assign a supervisor/operator to the machine from an effective instant. Mount only while open. */
export function AssignStaffDialog({
  machineId,
  timeZone,
  onClose,
  onAssigned,
}: AssignStaffDialogProps) {
  const keyFor = useIdempotencyKey();
  const [staff, setStaff] = useState<StaffDto | null>(null);
  const [initialValues] = useState<AssignValues>(() => ({
    staff_member_id: '',
    role: 'OPERATOR',
    effective_from: new Date().toISOString(),
  }));
  const fetchStaff = useCallback(
    async (q: string, signal: AbortSignal) =>
      (await staffService.list({ page: 1, page_size: 20, q }, signal)).items,
    [],
  );

  return (
    <FormDialog<AssignValues>
      open
      title="Assign staff"
      initialValues={initialValues}
      validationSchema={schema}
      submitLabel="Assign"
      onClose={onClose}
      onSubmit={async (v) => {
        const body: AssignIn = {
          staff_member_id: v.staff_member_id,
          role: v.role === 'SUPERVISOR' ? 'SUPERVISOR' : 'OPERATOR',
          effective_from: v.effective_from,
        };
        onAssigned(await machineService.assignStaff(machineId, body, keyFor(body)));
      }}
    >
      {(formik) => (
        <>
          <AsyncAutocomplete<StaffDto>
            label="Staff member"
            name="staff_member_id"
            required
            value={staff}
            fetchOptions={fetchStaff}
            getOptionLabel={(s) =>
              s.employee_code === null ? s.full_name : `${s.full_name} (${s.employee_code})`
            }
            isOptionEqualToValue={(a, b) => a.id === b.id}
            onChange={(s) => {
              setStaff(s);
              void formik.setFieldValue('staff_member_id', s?.id ?? '');
            }}
            onBlur={() => {
              void formik.setFieldTouched('staff_member_id', true);
            }}
            error={
              formik.touched.staff_member_id === true ? formik.errors.staff_member_id : undefined
            }
          />
          <FormikSelectField name="role" label="Role" options={ROLE_OPTIONS} required />
          <DateTimeField
            label="Effective from"
            name="effective_from"
            required
            timezone={timeZone}
            value={formik.values.effective_from === '' ? null : formik.values.effective_from}
            onChange={(next) => {
              void formik.setFieldValue('effective_from', next ?? '');
            }}
            error={formik.errors.effective_from}
          />
        </>
      )}
    </FormDialog>
  );
}
