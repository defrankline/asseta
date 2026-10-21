import { Stack } from '@mui/material';
import { useState } from 'react';
import { object, string } from 'yup';
import { trackerService } from '../../../api/services/trackerService';
import type { TrackerDto, TrackerUpdateIn } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { withErrorCode } from '../shared/errorHints';
import { orNull } from './trackerForms';
import { TRACKER_ERROR_HINTS } from './trackerLifecycle';

interface EditTrackerValues {
  label: string;
  sim_iccid: string;
  sim_msisdn: string;
  carrier: string;
  credentials_ref: string;
}

const schema = object({
  label: string().trim().required('Label is required').max(100, 'At most 100 characters'),
  sim_iccid: string().trim().max(32, 'At most 32 characters').default(''),
  sim_msisdn: string().trim().max(32, 'At most 32 characters').default(''),
  carrier: string().trim().max(60, 'At most 60 characters').default(''),
  credentials_ref: string().trim().max(200, 'At most 200 characters').default(''),
});

/** PUT body: the version that was read; a blank credentials reference keeps the stored one. */
function toTrackerUpdate(v: EditTrackerValues, version: number): TrackerUpdateIn {
  const credentials = orNull(v.credentials_ref);
  return {
    label: v.label.trim(),
    sim_iccid: orNull(v.sim_iccid),
    sim_msisdn: orNull(v.sim_msisdn),
    carrier: orNull(v.carrier),
    ...(credentials !== null ? { credentials_ref: credentials } : {}),
    version,
  };
}

interface EditTrackerDialogProps {
  tracker: TrackerDto;
  onClose: () => void;
  onSaved: (tracker: TrackerDto) => void;
  /** The server reported STALE_VERSION and the user chose Reload. */
  onReloadRequested: () => void;
}

/**
 * Edit label, SIM and carrier (device identity, model and assignment are not edited here).
 * Retired trackers are read-only. Mount only while open.
 */
export function EditTrackerDialog({
  tracker,
  onClose,
  onSaved,
  onReloadRequested,
}: EditTrackerDialogProps) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  const [initialValues] = useState<EditTrackerValues>(() => ({
    label: tracker.label,
    sim_iccid: tracker.sim_iccid ?? '',
    sim_msisdn: tracker.sim_msisdn ?? '',
    carrier: tracker.carrier ?? '',
    credentials_ref: '',
  }));
  const steps: FormStep<EditTrackerValues>[] = [
    {
      label: 'Device',
      fields: ['label', 'credentials_ref'],
      render: () => (
        <>
          <FormikTextField name="label" label="Label" required />
          <FormikTextField
            name="credentials_ref"
            label="Credentials reference"
            helperText="Leave blank to keep the stored reference."
          />
        </>
      ),
    },
    {
      label: 'SIM & carrier',
      fields: ['sim_iccid', 'sim_msisdn', 'carrier'],
      render: () => (
        <>
          <FormikTextField name="sim_iccid" label="SIM ICCID" />
          <FormikTextField name="sim_msisdn" label="SIM MSISDN" />
          <FormikTextField name="carrier" label="Carrier" />
        </>
      ),
    },
  ];
  return (
    <StepperFormDialog<EditTrackerValues>
      open
      title={`Edit tracker ${tracker.label}`}
      steps={steps}
      initialValues={initialValues}
      validationSchema={schema}
      submitLabel="Save changes"
      onClose={onClose}
      renderReview={(v) => (
        <Stack spacing={2}>
          {stale && (
            <StaleVersionAlert
              onReload={() => {
                onReloadRequested();
                onClose();
              }}
            />
          )}
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'External id', value: tracker.external_id },
              { label: 'Label', value: v.label },
              { label: 'SIM ICCID', value: v.sim_iccid === '' ? '—' : v.sim_iccid },
              { label: 'SIM MSISDN', value: v.sim_msisdn === '' ? '—' : v.sim_msisdn },
              { label: 'Carrier', value: v.carrier === '' ? '—' : v.carrier },
              {
                label: 'Credentials reference',
                value: v.credentials_ref === '' ? 'Unchanged' : v.credentials_ref,
              },
            ]}
          />
        </Stack>
      )}
      onSubmit={async (v) => {
        const body = toTrackerUpdate(v, tracker.version);
        try {
          onSaved(await guard(() => trackerService.update(tracker.id, body, keyFor(body))));
        } catch (err) {
          throw withErrorCode(err, TRACKER_ERROR_HINTS);
        }
      }}
    />
  );
}
