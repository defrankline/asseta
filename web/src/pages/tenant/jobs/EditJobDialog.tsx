import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { customerService } from '../../../api/services/customerService';
import { jobService } from '../../../api/services/jobService';
import { machineService } from '../../../api/services/machineService';
import { staffService } from '../../../api/services/staffService';
import type { JobDto, JobSiteDto } from '../../../api/types';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useSession } from '../../../session/useSession';
import { withErrorCode } from '../shared/errorHints';
import { contractLabel } from '../shared/jobDisplay';
import { jobSiteLabel } from '../shared/lookups';
import {
  ASSIGNMENT_FIELDS,
  JOB_EDIT_ERROR_HINTS,
  jobFormSchema,
  jobToValues,
  PRICING_FIELDS,
  SCHEDULE_FIELDS,
  toJobUpdatePayload,
  type JobFormValues,
} from './jobForm';
import { AssignmentFields, PricingFields, ScheduleFields } from './JobFormSteps';
import { JobReview } from './JobReview';

export interface EditJobDialogProps {
  job: JobDto;
  timeZone: string;
  onClose: () => void;
  /** Called with the saved job (new `version`, price re-derived by the server). */
  onSaved: (job: JobDto) => void;
  /** The server reported STALE_VERSION and the user chose Reload. */
  onReloadRequested: () => void;
}

function EditJobForm({
  job,
  initialValues,
  timeZone,
  onClose,
  onSaved,
  onReloadRequested,
}: EditJobDialogProps & { initialValues: JobFormValues }) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  const { hasPermission } = useSession();
  const [site, setSite] = useState<JobSiteDto | null>(null);
  const siteLabel = (id: string | null) =>
    id !== null && site?.id === id ? jobSiteLabel(site) : (id ?? '—');
  const locked = {
    contract: initialValues.contract === null ? '—' : contractLabel(initialValues.contract),
    jobNumber: job.job_number,
  };
  const steps: FormStep<JobFormValues>[] = [
    {
      label: 'Assignment',
      fields: ASSIGNMENT_FIELDS,
      render: () => (
        <AssignmentFields
          showSite={hasPermission(PERMISSIONS.tenantGeofenceRead)}
          onSiteChange={setSite}
          locked={locked}
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
      title={`Edit job ${job.job_number}`}
      steps={steps}
      initialValues={initialValues}
      validationSchema={jobFormSchema}
      submitLabel="Save changes"
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
          <JobReview v={v} timeZone={timeZone} siteLabel={siteLabel} />
        </Stack>
      )}
      onClose={onClose}
      onSubmit={async (values) => {
        const payload = toJobUpdatePayload(values, job.version);
        try {
          onSaved(await guard(() => jobService.update(job.id, payload, keyFor(payload))));
        } catch (err) {
          throw withErrorCode(err, JOB_EDIT_ERROR_HINTS);
        }
      }}
    />
  );
}

/**
 * Edit a DRAFT or PENDING_APPROVAL job (contract and job number fixed). Loads the contract,
 * machine and supervisor so the pickers show their labels. Mount only while open.
 */
export function EditJobDialog(props: EditJobDialogProps) {
  const { job, onClose } = props;
  const load = useCallback(
    async (signal: AbortSignal) => {
      const [contract, machine, supervisor] = await Promise.all([
        customerService.getContract(job.contract_id, signal),
        machineService.get(job.machine_id, signal),
        job.supervisor_id === null ? null : staffService.get(job.supervisor_id, signal),
      ]);
      return jobToValues(job, contract, machine, supervisor);
    },
    [job],
  );
  const resource = useAsyncResource(load);
  if (resource.data !== null) return <EditJobForm {...props} initialValues={resource.data} />;
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm" aria-labelledby="edit-job-loading">
      <DialogTitle id="edit-job-loading">{`Edit job ${job.job_number}`}</DialogTitle>
      <DialogContent>
        <AsyncContent
          resource={resource}
          errorTitle="Could not load the job details"
          loadingLabel="Loading job"
        >
          {() => null}
        </AsyncContent>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
      </DialogActions>
    </Dialog>
  );
}
