import { useState } from 'react';
import { jobService } from '../../../api/services/jobService';
import { PERMISSIONS } from '../../../access/permissionCodes';
import type { JobDto, JobSiteDto } from '../../../api/types';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useSession } from '../../../session/useSession';
import { withErrorCode } from '../shared/errorHints';
import { JOB_ERROR_HINTS } from '../shared/jobDisplay';
import { jobSiteLabel } from '../shared/lookups';
import {
  ASSIGNMENT_FIELDS,
  emptyJobValues,
  jobFormSchema,
  PRICING_FIELDS,
  SCHEDULE_FIELDS,
  toJobPayload,
  type JobFormValues,
} from './jobForm';
import { AssignmentFields, PricingFields, ScheduleFields } from './JobFormSteps';
import { JobReview } from './JobReview';

interface CreateJobDialogProps {
  timeZone: string;
  onClose: () => void;
  onCreated: (job: JobDto) => void;
}

/** Assignment → Schedule → Pricing → Review. New jobs start as DRAFT. Mount only while open. */
export function CreateJobDialog({ timeZone, onClose, onCreated }: CreateJobDialogProps) {
  const keyFor = useIdempotencyKey();
  const { hasPermission } = useSession();
  const [site, setSite] = useState<JobSiteDto | null>(null);
  const siteLabel = (id: string | null) =>
    id !== null && site?.id === id ? jobSiteLabel(site) : (id ?? '—');
  const [initialValues] = useState(() => emptyJobValues(new Date().toISOString()));
  const steps: FormStep<JobFormValues>[] = [
    {
      label: 'Assignment',
      fields: ASSIGNMENT_FIELDS,
      render: () => (
        <AssignmentFields
          showSite={hasPermission(PERMISSIONS.tenantGeofenceRead)}
          onSiteChange={setSite}
        />
      ),
    },
    {
      label: 'Schedule',
      fields: SCHEDULE_FIELDS,
      render: () => <ScheduleFields timeZone={timeZone} />,
    },
    {
      label: 'Pricing',
      fields: PRICING_FIELDS,
      render: (formik) => <PricingFields formik={formik} />,
    },
  ];
  return (
    <StepperFormDialog<JobFormValues>
      open
      title="New job"
      steps={steps}
      initialValues={initialValues}
      validationSchema={jobFormSchema}
      submitLabel="Create job"
      renderReview={(v) => <JobReview v={v} timeZone={timeZone} siteLabel={siteLabel} />}
      onClose={onClose}
      onSubmit={async (values) => {
        const payload = toJobPayload(values);
        try {
          onCreated(await jobService.create(payload, keyFor(payload)));
        } catch (err) {
          throw withErrorCode(err, JOB_ERROR_HINTS);
        }
      }}
    />
  );
}
