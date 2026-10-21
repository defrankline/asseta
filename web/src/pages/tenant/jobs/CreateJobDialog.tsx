import { Alert } from '@mui/material';
import { useState } from 'react';
import { jobService } from '../../../api/services/jobService';
import { PERMISSIONS } from '../../../access/permissionCodes';
import type { JobDto, JobSiteDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useSession } from '../../../session/useSession';
import { formatPercent } from '../../../utils/money';
import { formatInstantIn } from '../../../utils/time';
import { machineLabel } from '../shared/display';
import { withErrorCode } from '../shared/errorHints';
import { contractLabel, JOB_ERROR_HINTS, STANDBY_OPTIONS } from '../shared/jobDisplay';
import { jobSiteLabel } from '../shared/lookups';
import { labelOf } from '../shared/display';
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

interface CreateJobDialogProps {
  timeZone: string;
  onClose: () => void;
  onCreated: (job: JobDto) => void;
}

function money(amount: string, currency: string | undefined) {
  return currency === undefined ? amount : <MoneyText amount={amount} currency={currency} />;
}

function JobReview({
  v,
  timeZone,
  siteLabel,
}: {
  v: JobFormValues;
  timeZone: string;
  siteLabel: (id: string | null) => string;
}) {
  const currency = v.contract?.currency;
  const negotiated = v.rate_mode === 'NEGOTIATED';
  return (
    <>
      <Alert severity={negotiated ? 'warning' : 'info'}>
        {negotiated ? (
          <>
            Rate source: <strong>Negotiated</strong> — {money(v.hourly_rate.trim(), currency)} per
            hour for this job only (overrides the rate card).
          </>
        ) : (
          <>
            Rate source: <strong>Tenant rate card</strong> — resolved by the server for the
            machine&apos;s category at the planned start and snapshotted on the job.
          </>
        )}
      </Alert>
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Contract', value: v.contract === null ? '—' : contractLabel(v.contract) },
          { label: 'Job number', value: v.job_number.trim() },
          { label: 'Machine', value: v.machine === null ? '—' : machineLabel(v.machine) },
          { label: 'Supervisor', value: v.supervisor?.full_name ?? '—' },
          {
            label: 'Job site',
            value: v.job_site_id === '' ? "Contract's default" : siteLabel(v.job_site_id),
          },
          { label: 'Planned start', value: formatInstantIn(v.planned_start, timeZone) },
          {
            label: 'Planned end',
            value: v.planned_end === '' ? '—' : formatInstantIn(v.planned_end, timeZone),
          },
          {
            label: 'Hourly rate',
            value: negotiated ? money(v.hourly_rate.trim(), currency) : 'From rate card',
          },
          {
            label: 'Minimum hours',
            value:
              v.minimum_hours.trim() === ''
                ? negotiated
                  ? 'None'
                  : 'From rate card'
                : `${v.minimum_hours.trim()} h`,
          },
          { label: 'Standby', value: labelOf(STANDBY_OPTIONS, v.standby_treatment) },
          ...(v.standby_treatment === 'STANDBY_RATE'
            ? [{ label: 'Standby rate', value: money(v.standby_rate.trim(), currency) }]
            : []),
          { label: 'Mobilization fee', value: money(v.mobilization_fee.trim(), currency) },
          { label: 'Discount', value: formatPercent(v.discount_percent.trim()) },
          { label: 'Tax rate', value: formatPercent(v.tax_rate_percent.trim()) },
        ]}
      />
    </>
  );
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
