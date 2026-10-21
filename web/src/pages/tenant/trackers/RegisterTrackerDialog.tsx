import { Alert, Box, Chip, Stack, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { object, string } from 'yup';
import { trackerService } from '../../../api/services/trackerService';
import type { TrackerDto, TrackerIn, TrackerModelDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { ErrorState } from '../../../components/feedback/ErrorState';
import { LoadingState } from '../../../components/feedback/LoadingState';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { CAPABILITY_LABELS } from '../shared/display';
import { orNull } from './trackerForms';

interface RegisterValues {
  tracker_model_id: string;
  external_id: string;
  label: string;
  sim_iccid: string;
  sim_msisdn: string;
  carrier: string;
  credentials_ref: string;
}

const INITIAL: RegisterValues = {
  tracker_model_id: '',
  external_id: '',
  label: '',
  sim_iccid: '',
  sim_msisdn: '',
  carrier: '',
  credentials_ref: '',
};

const schema = object({
  tracker_model_id: string().required('Select an approved tracker model'),
  external_id: string()
    .trim()
    .required('External device id is required')
    .min(3, 'At least 3 characters')
    .max(100, 'At most 100 characters'),
  label: string().trim().required('Label is required').max(100, 'At most 100 characters'),
  sim_iccid: string().trim().max(32, 'At most 32 characters').default(''),
  sim_msisdn: string().trim().max(32, 'At most 32 characters').default(''),
  carrier: string().trim().max(60, 'At most 60 characters').default(''),
  credentials_ref: string().trim().max(200, 'At most 200 characters').default(''),
});

function toPayload(v: RegisterValues): TrackerIn {
  return {
    tracker_model_id: v.tracker_model_id,
    external_id: v.external_id.trim(),
    label: v.label.trim(),
    sim_iccid: orNull(v.sim_iccid),
    sim_msisdn: orNull(v.sim_msisdn),
    carrier: orNull(v.carrier),
    credentials_ref: orNull(v.credentials_ref),
  };
}

function modelName(m: TrackerModelDto): string {
  return `${m.manufacturer} ${m.model}`;
}

export function ModelInfo({ model }: { model: TrackerModelDto }) {
  return (
    <Alert severity="info">
      <Stack spacing={1}>
        <Typography variant="body2">
          {modelName(model)} · protocol {model.protocol} · adapter {model.adapter}
        </Typography>
        <Typography variant="caption">
          Declared capabilities (vendor claims — verified only once the device reports them):
        </Typography>
        <Box className="flex flex-wrap gap-1">
          {model.declared_capabilities.length === 0
            ? '—'
            : model.declared_capabilities.map((c) => (
                <Chip key={c} size="small" variant="outlined" label={CAPABILITY_LABELS[c]} />
              ))}
        </Box>
      </Stack>
    </Alert>
  );
}

interface RegisterTrackerDialogProps {
  onClose: () => void;
  onRegistered: (tracker: TrackerDto) => void;
}

/** Device → Connectivity → Review. Mount only while open. */
export function RegisterTrackerDialog({ onClose, onRegistered }: RegisterTrackerDialogProps) {
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState(INITIAL);
  const load = useCallback((signal: AbortSignal) => trackerService.listModels(signal), []);
  const models = useAsyncResource(load);
  const list = models.data ?? [];
  const find = (id: string) => list.find((m) => m.id === id);

  const steps: FormStep<RegisterValues>[] = [
    {
      label: 'Device',
      fields: ['tracker_model_id', 'external_id', 'label'],
      render: (f) => {
        if (models.error !== null)
          return <ErrorState error={models.error} title="Could not load tracker models" />;
        if (models.data === null) return <LoadingState label="Loading approved models" />;
        const selected = find(f.values.tracker_model_id);
        return (
          <>
            {list.length === 0 && (
              <Alert severity="warning">
                No approved tracker models are available. Ask the platform operator to approve a
                driver/model first.
              </Alert>
            )}
            <FormikSelectField
              name="tracker_model_id"
              label="Approved tracker model"
              required
              options={list.map((m) => ({ value: m.id, label: modelName(m) }))}
            />
            {selected !== undefined && <ModelInfo model={selected} />}
            <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormikTextField
                name="external_id"
                label="External device id"
                required
                helperText="e.g. IMEI / Traccar unique id"
              />
              <FormikTextField name="label" label="Label" required />
            </Box>
          </>
        );
      },
    },
    {
      label: 'Connectivity',
      fields: ['sim_iccid', 'sim_msisdn', 'carrier', 'credentials_ref'],
      render: () => (
        <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormikTextField name="sim_iccid" label="SIM ICCID" />
          <FormikTextField name="sim_msisdn" label="SIM MSISDN" />
          <FormikTextField name="carrier" label="Carrier" />
          <FormikTextField
            name="credentials_ref"
            label="Credentials reference"
            helperText="Reference to a secret store entry — never the secret itself"
          />
        </Box>
      ),
    },
  ];

  return (
    <StepperFormDialog<RegisterValues>
      open
      title="Register tracker"
      steps={steps}
      initialValues={initialValues}
      validationSchema={schema}
      submitLabel="Register tracker"
      onClose={onClose}
      renderReview={(v) => {
        const m = find(v.tracker_model_id);
        return (
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Model', value: m !== undefined ? modelName(m) : '—' },
              { label: 'External device id', value: v.external_id },
              { label: 'Label', value: v.label },
              { label: 'SIM ICCID', value: orNull(v.sim_iccid) ?? '—' },
              { label: 'SIM MSISDN', value: orNull(v.sim_msisdn) ?? '—' },
              { label: 'Carrier', value: orNull(v.carrier) ?? '—' },
              { label: 'Credentials reference', value: orNull(v.credentials_ref) ?? '—' },
            ]}
          />
        );
      }}
      onSubmit={async (values) => {
        const payload = toPayload(values);
        const tracker = await trackerService.register(payload, keyFor(payload));
        onRegistered(tracker);
      }}
    />
  );
}
