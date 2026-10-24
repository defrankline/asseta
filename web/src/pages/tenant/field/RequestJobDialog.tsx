import { Alert } from '@mui/material';
import { useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { newUuid } from '../../../api/ids';
import { jobService } from '../../../api/services/jobService';
import type { FieldContractDto, JobDto, JobSiteDto, MachineDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikDateTimeField } from '../../../components/forms/FormikDateTimeField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { machineLabel } from '../shared/display';
import { withErrorCode } from '../shared/errorHints';
import { JOB_ERROR_HINTS } from '../shared/jobDisplay';
import { FormikJobSitePicker } from '../shared/lookupPickers';
import { jobSiteLabel } from '../shared/lookups';
import { FormikFieldContractIdPicker, FormikFieldMachineIdPicker } from './fieldPickers';
import {
  emptyRequestValues,
  fieldContractLabel,
  REQUEST_NOTE_MAX,
  REQUEST_WHAT_FIELDS,
  REQUEST_WHEN_FIELDS,
  requestJobSchema,
  toRequestPayload,
  type RequestJobValues,
} from './requestJob';

interface RequestJobDialogProps {
  timeZone: string;
  onClose: () => void;
  onRequested: (job: JobDto) => void;
}

/**
 * Request a job from the field (customer, machine, when, what was asked for). The server numbers and
 * prices it and sends it to the owner for approval. Mount only while open (one request per open).
 */
export function RequestJobDialog({ timeZone, onClose, onRequested }: RequestJobDialogProps) {
  const keyFor = useIdempotencyKey();
  const { hasPermission } = useSession();
  const [clientId] = useState(() => newUuid());
  const [initialValues] = useState(() => emptyRequestValues(new Date().toISOString()));
  const [contract, setContract] = useState<FieldContractDto | null>(null);
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [site, setSite] = useState<JobSiteDto | null>(null);
  const contractSite = contract?.job_site_name ?? null;
  const siteText = (id: string) => {
    if (id === '') return contractSite ?? "The contract's site";
    return site?.id === id ? jobSiteLabel(site) : id;
  };
  const steps: FormStep<RequestJobValues>[] = [
    {
      label: 'Customer & machine',
      fields: REQUEST_WHAT_FIELDS,
      render: () => (
        <>
          <FormikFieldContractIdPicker
            name="contract_id"
            label="Customer — contract"
            required
            onOptionChange={setContract}
          />
          <FormikFieldMachineIdPicker
            name="machine_id"
            label="Machine"
            required
            onOptionChange={setMachine}
          />
          {hasPermission(PERMISSIONS.tenantGeofenceRead) && (
            <FormikJobSitePicker
              name="job_site_id"
              label="Job site (optional)"
              helperText={
                contractSite === null
                  ? "Empty = the contract's site"
                  : `Empty = the contract's site (${contractSite})`
              }
              onOptionChange={setSite}
            />
          )}
        </>
      ),
    },
    {
      label: 'When & what',
      fields: REQUEST_WHEN_FIELDS,
      render: () => (
        <>
          <FormikDateTimeField
            name="planned_start"
            label="Planned start"
            timeZone={timeZone}
            required
          />
          <FormikDateTimeField
            name="planned_end"
            label="Planned end (optional)"
            timeZone={timeZone}
          />
          <FormikTextField
            name="note"
            label="What the customer asked for (optional)"
            multiline
            minRows={3}
            helperText={`Shown to the owner when approving. At most ${String(REQUEST_NOTE_MAX)} characters.`}
          />
        </>
      ),
    },
  ];
  return (
    <StepperFormDialog<RequestJobValues>
      open
      title="Request a job"
      steps={steps}
      initialValues={initialValues}
      validationSchema={requestJobSchema}
      submitLabel="Send request"
      renderReview={(v) => (
        <>
          <Alert severity="info">
            The job number and price are set by the office. The job waits for the owner&apos;s
            approval before it can start.
          </Alert>
          <KeyValueGrid
            columns={2}
            items={[
              {
                label: 'Customer — contract',
                value: contract === null ? '—' : fieldContractLabel(contract),
              },
              { label: 'Machine', value: machine === null ? '—' : machineLabel(machine) },
              { label: 'Job site', value: siteText(v.job_site_id) },
              { label: 'Planned start', value: formatInstantIn(v.planned_start, timeZone) },
              {
                label: 'Planned end',
                value: v.planned_end === '' ? '—' : formatInstantIn(v.planned_end, timeZone),
              },
              { label: 'Note', value: v.note.trim() === '' ? '—' : v.note.trim() },
            ]}
          />
        </>
      )}
      onClose={onClose}
      onSubmit={async (values) => {
        const payload = toRequestPayload(values, clientId);
        try {
          onRequested(await jobService.request(payload, keyFor(payload)));
        } catch (err) {
          throw withErrorCode(err, JOB_ERROR_HINTS);
        }
      }}
    />
  );
}
