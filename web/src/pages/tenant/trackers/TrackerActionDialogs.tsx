import { object } from 'yup';
import { useState } from 'react';
import { trackerService } from '../../../api/services/trackerService';
import type { ProvisioningState, TrackerDto } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { FormikDateTimeField } from './trackerFields';
import {
  instantSchema,
  reasonSchema,
  stateSchema,
  stateTargetOptions,
  type StateValues,
} from './trackerForms';

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

/** Suspend / retire / reactivate. Mount only while open. */
export function TrackerStateDialog({ tracker, onClose, onDone }: ActionProps) {
  const keyFor = useIdempotencyKey();
  const options = stateTargetOptions(tracker.provisioning_state);
  const [initialValues] = useState<StateValues>(() => ({
    state: options[0]?.value ?? '',
    reason: '',
  }));
  return (
    <FormDialog<StateValues>
      open
      title={`Change state · ${tracker.label}`}
      initialValues={initialValues}
      validationSchema={stateSchema}
      submitLabel="Change state"
      onClose={onClose}
      onSubmit={async (v) => {
        if (v.state === '') return;
        const body = { state: v.state satisfies ProvisioningState, reason: v.reason.trim() };
        onDone(await trackerService.changeState(tracker.id, body, keyFor(body)));
      }}
    >
      <FormikSelectField name="state" label="New state" options={options} required />
      <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
    </FormDialog>
  );
}
