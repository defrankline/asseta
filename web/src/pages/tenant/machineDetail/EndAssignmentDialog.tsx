import { Typography } from '@mui/material';
import { useState } from 'react';
import { object, string, type ObjectSchema } from 'yup';
import { machineService } from '../../../api/services/machineService';
import type { AssignmentDto, EndAssignmentIn } from '../../../api/types';
import { DateTimeField } from '../../../components/forms/DateTimeField';
import { FormDialog } from '../../../components/forms/FormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../utils/time';

interface EndValues {
  effective_to: string;
}

const schema: ObjectSchema<EndValues> = object({
  effective_to: string().required('End time is required'),
});

interface EndAssignmentDialogProps {
  assignment: AssignmentDto;
  staffName: string;
  timeZone: string;
  onClose: () => void;
  onEnded: (assignment: AssignmentDto) => void;
}

/** End an open staff assignment at an instant (after its start). Mount only while open. */
export function EndAssignmentDialog({
  assignment,
  staffName,
  timeZone,
  onClose,
  onEnded,
}: EndAssignmentDialogProps) {
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState<EndValues>(() => ({ effective_to: new Date().toISOString() }));
  return (
    <FormDialog<EndValues>
      open
      title={`End assignment · ${staffName}`}
      initialValues={initialValues}
      validationSchema={schema}
      submitLabel="End assignment"
      onClose={onClose}
      onSubmit={async (v) => {
        const body: EndAssignmentIn = { effective_to: v.effective_to };
        onEnded(await machineService.endAssignment(assignment.id, body, keyFor(body)));
      }}
    >
      {(formik) => (
        <>
          <Typography variant="body2" color="text.secondary">
            Assigned since {formatInstantIn(assignment.effective_from, timeZone)}.
          </Typography>
          <DateTimeField
            label="Ends at"
            name="effective_to"
            required
            timezone={timeZone}
            minDateTime={assignment.effective_from}
            value={formik.values.effective_to === '' ? null : formik.values.effective_to}
            onChange={(next) => {
              void formik.setFieldValue('effective_to', next ?? '');
            }}
            error={formik.errors.effective_to}
          />
        </>
      )}
    </FormDialog>
  );
}
