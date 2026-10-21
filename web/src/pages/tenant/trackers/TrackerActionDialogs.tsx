import { object } from 'yup';
import { useState } from 'react';
import { trackerService } from '../../../api/services/trackerService';
import type { TrackerDto } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { FormikDateTimeField } from './trackerFields';
import { instantSchema, reasonSchema } from './trackerForms';

interface ActionProps {
  tracker: TrackerDto;
  onClose: () => void;
  onDone: (tracker: TrackerDto) => void;
}

interface UnassignValues {
  effective_to: string;
  reason: string;
}

const unassignSchema = object({
  effective_to: instantSchema('Effective to'),
  reason: reasonSchema(true),
});

/** End the tracker's current assignment. Mount only while open. */
export function UnassignTrackerDialog({
  tracker,
  timeZone,
  onClose,
  onDone,
}: ActionProps & { timeZone: string }) {
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState<UnassignValues>(() => ({
    effective_to: new Date().toISOString(),
    reason: '',
  }));
  return (
    <FormDialog<UnassignValues>
      open
      title={`Unassign · ${tracker.label}`}
      initialValues={initialValues}
      validationSchema={unassignSchema}
      submitLabel="Unassign"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = { effective_to: v.effective_to, reason: v.reason.trim() };
        onDone(await trackerService.unassign(tracker.id, body, keyFor(body)));
      }}
    >
      <FormikDateTimeField name="effective_to" label="Effective to" timeZone={timeZone} required />
      <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
    </FormDialog>
  );
}
