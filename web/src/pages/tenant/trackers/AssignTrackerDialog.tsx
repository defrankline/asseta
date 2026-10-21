import { Alert, AlertTitle, Box, Typography } from '@mui/material';
import { useFormikContext } from 'formik';
import { useState } from 'react';
import { ApiError } from '../../../api/ApiError';
import { trackerService } from '../../../api/services/trackerService';
import type {
  AssignTrackerIn,
  MachineDto,
  TrackerAssignmentDto,
  TrackerDto,
} from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../utils/time';
import { MachinePicker } from '../shared/MachinePicker';
import { FormikDateTimeField, FormikToggle } from './trackerFields';
import { assignSchema, orNull, type AssignValues } from './trackerForms';

export const SWAP_WARNING =
  "Swap: the machine's current primary tracker assignment will be ended at the effective time and this tracker becomes primary.";

const ERROR_HINTS: Readonly<Record<string, string>> = {
  PRIMARY_TRACKER_EXISTS:
    'This machine already has a primary tracker. Enable "Replace existing primary (swap)" to swap it.',
  TRACKER_ASSIGNED: 'This tracker is assigned to another machine; unassign it first.',
  MACHINE_NOT_ENROLLED: 'The machine must be an enrolled billable asset before it can be tracked.',
  TRACKER_NOT_ASSIGNABLE: 'The tracker cannot be assigned in its current state.',
  ASSIGNMENT_DATES: 'Check the effective time (a swap must start after the current primary).',
};

/** Adds an actionable hint to known business-rule errors (code and correlation id kept). */
function withHint(err: unknown): unknown {
  if (!(err instanceof ApiError)) return err;
  const hint = ERROR_HINTS[err.code];
  if (hint === undefined) return err;
  return new ApiError({
    status: err.status,
    code: err.code,
    message: `${err.message} — ${hint}`,
    correlationId: err.correlationId,
    details: err.details,
  });
}

function MachineField() {
  const { values, errors, touched, setFieldValue, setFieldTouched } =
    useFormikContext<AssignValues>();
  const [picked, setPicked] = useState<MachineDto | null>(null);
  const value = picked !== null && picked.id === values.machine_id ? picked : null;
  return (
    <MachinePicker
      name="machine_id"
      required
      value={value}
      error={touched.machine_id === true ? errors.machine_id : undefined}
      onBlur={() => void setFieldTouched('machine_id', true)}
      onChange={(m) => {
        setPicked(m);
        void setFieldValue('machine_id', m?.id ?? '');
        void setFieldValue('machine_label', m === null ? '' : `${m.asset_code} · ${m.name}`);
      }}
    />
  );
}

function SwapWarning() {
  return (
    <Alert severity="warning" role="alert">
      <AlertTitle>Swap primary tracker</AlertTitle>
      {SWAP_WARNING}
    </Alert>
  );
}

interface AssignTrackerDialogProps {
  tracker: TrackerDto;
  timeZone: string;
  onClose: () => void;
  onAssigned: (assignment: TrackerAssignmentDto) => void;
}

/** Machine → Options → Review. Mount only while open. */
export function AssignTrackerDialog({
  tracker,
  timeZone,
  onClose,
  onAssigned,
}: AssignTrackerDialogProps) {
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState<AssignValues>(() => ({
    machine_id: '',
    machine_label: '',
    is_primary: true,
    effective_from: new Date().toISOString(),
    replace_existing_primary: false,
    reason: '',
  }));

  const steps: FormStep<AssignValues>[] = [
    {
      label: 'Machine',
      fields: ['machine_id', 'effective_from'],
      render: () => (
        <>
          <Typography variant="body2" color="text.secondary">
            Assign tracker {tracker.label} ({tracker.external_id}) to a machine. One active primary
            tracker per machine.
          </Typography>
          <MachineField />
          <FormikDateTimeField
            name="effective_from"
            label="Effective from"
            timeZone={timeZone}
            required
          />
        </>
      ),
    },
    {
      label: 'Options',
      fields: ['is_primary', 'replace_existing_primary', 'reason'],
      render: (f) => (
        <>
          <FormikToggle name="is_primary" label="Primary tracker for this machine" />
          <FormikToggle
            name="replace_existing_primary"
            label="Replace existing primary (swap)"
            variant="checkbox"
          />
          {f.values.replace_existing_primary && <SwapWarning />}
          <FormikTextField name="reason" label="Reason" multiline minRows={2} />
        </>
      ),
    },
  ];

  return (
    <StepperFormDialog<AssignValues>
      open
      title={`Assign / swap · ${tracker.label}`}
      steps={steps}
      initialValues={initialValues}
      validationSchema={assignSchema}
      submitLabel="Assign tracker"
      onClose={onClose}
      renderReview={(v) => (
        <Box className="flex flex-col gap-3">
          {v.replace_existing_primary && <SwapWarning />}
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Tracker', value: `${tracker.label} (${tracker.external_id})` },
              { label: 'Machine', value: v.machine_label || v.machine_id },
              { label: 'Effective from', value: formatInstantIn(v.effective_from, timeZone) },
              { label: 'Primary', value: v.is_primary ? 'Yes' : 'No' },
              {
                label: 'Replace existing primary',
                value: v.replace_existing_primary ? 'Yes — swap' : 'No',
              },
              { label: 'Reason', value: orNull(v.reason) ?? '—' },
            ]}
          />
        </Box>
      )}
      onSubmit={async (v) => {
        const payload: AssignTrackerIn = {
          machine_id: v.machine_id,
          is_primary: v.is_primary,
          effective_from: v.effective_from,
          replace_existing_primary: v.replace_existing_primary,
          reason: orNull(v.reason),
        };
        try {
          onAssigned(await trackerService.assign(tracker.id, payload, keyFor(payload)));
        } catch (err) {
          throw withHint(err);
        }
      }}
    />
  );
}
