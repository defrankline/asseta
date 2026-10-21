import { Box } from '@mui/material';
import { useState } from 'react';
import { mixed, object, type ObjectSchema } from 'yup';
import { newUuid } from '../../../api/ids';
import { ACTIVITY_TYPES } from '../../../api/services/jobSchemas';
import { jobService } from '../../../api/services/jobService';
import type { ActivityDto, ActivityIn, ActivityType, JobDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikDateTimeField } from '../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../utils/time';
import { labelOf } from '../shared/display';
import { withErrorCode } from '../shared/errorHints';
import {
  isAfter,
  optionalInstant,
  optionalText,
  orNull,
  requiredInstant,
} from '../shared/formRules';
import { ACTIVITY_TYPE_OPTIONS, JOB_ERROR_HINTS, STANDBY_OPTIONS } from '../shared/jobDisplay';

type BillableChoice = '' | 'true' | 'false';

interface ActivityValues {
  activity_type: ActivityType;
  billable: BillableChoice;
  note: string;
  started_at: string;
  ended_at: string;
}

const BILLABLE_OPTIONS = [
  { value: '', label: 'Default (from type and job standby terms)' },
  { value: 'true', label: 'Billable' },
  { value: 'false', label: 'Non-billable' },
];

const schema: ObjectSchema<ActivityValues> = object({
  activity_type: mixed<ActivityType>().oneOf(ACTIVITY_TYPES).required('Choose a type'),
  billable: mixed<BillableChoice>().oneOf(['', 'true', 'false']).default(''),
  note: optionalText('Note', 2000),
  started_at: requiredInstant('Start'),
  ended_at: optionalInstant().test('after', 'End must be after the start', function (v) {
    return isAfter((this.parent as ActivityValues).started_at, v);
  }),
});

interface ActivityDialogProps {
  job: JobDto;
  timeZone: string;
  onClose: () => void;
  onLogged: (activity: ActivityDto) => void;
}

/** Activity → Time → Review. `client_id` is fixed per open so retries never duplicate the entry. */
export function ActivityDialog({ job, timeZone, onClose, onLogged }: ActivityDialogProps) {
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(newUuid);
  const [initialValues] = useState<ActivityValues>(() => ({
    activity_type: 'WORK',
    billable: '',
    note: '',
    started_at: new Date().toISOString(),
    ended_at: '',
  }));
  const toPayload = (v: ActivityValues): ActivityIn => ({
    client_id: clientId,
    activity_type: v.activity_type,
    started_at: v.started_at,
    ended_at: orNull(v.ended_at),
    billable: v.billable === '' ? null : v.billable === 'true',
    note: orNull(v.note),
  });
  const steps: FormStep<ActivityValues>[] = [
    {
      label: 'Activity',
      fields: ['activity_type', 'billable', 'note'],
      render: () => (
        <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormikSelectField
            name="activity_type"
            label="Type"
            options={ACTIVITY_TYPE_OPTIONS}
            required
          />
          <FormikSelectField
            name="billable"
            label="Billable override"
            options={BILLABLE_OPTIONS}
            helperText={`Job standby terms: ${labelOf(STANDBY_OPTIONS, job.standby_treatment)}`}
          />
          <Box className="sm:col-span-2">
            <FormikTextField name="note" label="Note (e.g. downtime cause)" multiline minRows={2} />
          </Box>
        </Box>
      ),
    },
    {
      label: 'Time',
      fields: ['started_at', 'ended_at'],
      render: () => (
        <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormikDateTimeField name="started_at" label="Start" timeZone={timeZone} required />
          <FormikDateTimeField
            name="ended_at"
            label="End (optional)"
            timeZone={timeZone}
            helperText="Open periods do not count towards non-billable hours"
          />
        </Box>
      ),
    },
  ];
  return (
    <StepperFormDialog<ActivityValues>
      open
      title={`Log activity · ${job.job_number}`}
      steps={steps}
      initialValues={initialValues}
      validationSchema={schema}
      submitLabel="Log activity"
      renderReview={(v) => (
        <KeyValueGrid
          columns={2}
          items={[
            { label: 'Type', value: labelOf(ACTIVITY_TYPE_OPTIONS, v.activity_type) },
            { label: 'Billable', value: labelOf(BILLABLE_OPTIONS, v.billable) },
            { label: 'Start', value: formatInstantIn(v.started_at, timeZone) },
            {
              label: 'End',
              value: v.ended_at === '' ? 'Open' : formatInstantIn(v.ended_at, timeZone),
            },
            { label: 'Note', value: v.note.trim() || '—' },
          ]}
        />
      )}
      onClose={onClose}
      onSubmit={async (values) => {
        const payload = toPayload(values);
        try {
          onLogged(await jobService.logActivity(job.id, payload, keyFor(payload)));
        } catch (err) {
          throw withErrorCode(err, JOB_ERROR_HINTS);
        }
      }}
    />
  );
}
