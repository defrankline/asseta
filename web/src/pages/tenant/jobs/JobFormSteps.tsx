import {
  Alert,
  Box,
  FormControl,
  FormControlLabel,
  FormLabel,
  Radio,
  RadioGroup,
  TextField,
  Typography,
} from '@mui/material';
import type { FormikProps } from 'formik';
import type { BillingMode } from '../../../api/hoursTypes';
import type { JobSiteDto } from '../../../api/types';
import { FormikDateTimeField } from '../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { BILLING_MODE_LABELS } from '../hours/hoursDisplay';
import { STANDBY_OPTIONS } from '../shared/jobDisplay';
import {
  FormikContractPicker,
  FormikMachinePicker,
  FormikSupervisorPicker,
} from '../shared/pickers';
import { FormikJobSitePicker } from '../shared/lookupPickers';
import type { JobFormValues } from './jobForm';

const grid = 'grid grid-cols-1 gap-4 sm:grid-cols-2';
const decimal = { htmlInput: { inputMode: 'decimal' as const } };

interface AssignmentFieldsProps {
  /** Show the job-site picker (needs `tenant.geofence.read`). */
  showSite: boolean;
  onSiteChange: (site: JobSiteDto | null) => void;
  /** Edit: contract and job number are fixed and shown read-only. */
  locked?: { contract: string; jobNumber: string };
}

export function AssignmentFields({ showSite, onSiteChange, locked }: AssignmentFieldsProps) {
  return (
    <Box className={grid}>
      {locked === undefined ? (
        <>
          <FormikContractPicker name="contract" label="Contract" required />
          <FormikTextField name="job_number" label="Job number" required />
        </>
      ) : (
        <>
          <TextField
            label="Contract"
            value={locked.contract}
            disabled
            helperText="The contract cannot be changed"
          />
          <TextField label="Job number" value={locked.jobNumber} disabled />
        </>
      )}
      <FormikMachinePicker name="machine" label="Machine" required />
      <FormikSupervisorPicker
        name="supervisor"
        label="Supervisor"
        helperText="Searches staff of kind Supervisor"
      />
      {showSite && (
        <FormikJobSitePicker
          name="job_site_id"
          label="Job site"
          helperText="Empty = the contract's default site"
          onOptionChange={onSiteChange}
        />
      )}
    </Box>
  );
}

export function ScheduleFields({ timeZone }: { timeZone: string }) {
  return (
    <Box className={grid}>
      <FormikDateTimeField
        name="planned_start"
        label="Planned start"
        timeZone={timeZone}
        required
        helperText="The rate card in force at this time is used"
      />
      <FormikDateTimeField name="planned_end" label="Planned end (optional)" timeZone={timeZone} />
    </Box>
  );
}

/** Billing choice when customer hours are on: modes allowed by the tenant policy, default first. */
type ModesKey = 'INVOICE' | 'PREPAID_HOURS' | 'INVOICE,PREPAID_HOURS';
type Options = readonly { value: string; label: string }[];
const modesKey = (b: BillingChoice): ModesKey =>
  b.modes.includes('INVOICE')
    ? b.modes.includes('PREPAID_HOURS')
      ? 'INVOICE,PREPAID_HOURS'
      : 'INVOICE'
    : 'PREPAID_HOURS';
const optionsFor = (defaultMode: BillingMode, modes: readonly BillingMode[]): Options => [
  { value: '', label: `Company default (${BILLING_MODE_LABELS[defaultMode]})` },
  ...modes.map((m) => ({ value: m, label: BILLING_MODE_LABELS[m] })),
];
type BillingKey = `${BillingMode}/${ModesKey}`;
const billingKey = (b: BillingChoice): BillingKey => `${b.defaultMode}/${modesKey(b)}`;
/** Code-defined select options per (company default, allowed modes) of the tenant policy. */
const BILLING_OPTIONS: Readonly<Record<BillingKey, Options>> = {
  'INVOICE/INVOICE': optionsFor('INVOICE', ['INVOICE']),
  'INVOICE/PREPAID_HOURS': optionsFor('INVOICE', ['PREPAID_HOURS']),
  'INVOICE/INVOICE,PREPAID_HOURS': optionsFor('INVOICE', ['INVOICE', 'PREPAID_HOURS']),
  'PREPAID_HOURS/INVOICE': optionsFor('PREPAID_HOURS', ['INVOICE']),
  'PREPAID_HOURS/PREPAID_HOURS': optionsFor('PREPAID_HOURS', ['PREPAID_HOURS']),
  'PREPAID_HOURS/INVOICE,PREPAID_HOURS': optionsFor('PREPAID_HOURS', ['INVOICE', 'PREPAID_HOURS']),
};

export interface BillingChoice {
  modes: readonly BillingMode[];
  defaultMode: BillingMode;
}

export function PricingFields({
  formik,
  billing = null,
}: {
  formik: FormikProps<JobFormValues>;
  /** null: customer hours off (or unknown) — every job is invoiced as before. */
  billing?: BillingChoice | null;
}) {
  const { values, setFieldValue } = formik;
  return (
    <>
      {billing !== null && billing.modes.length > 0 && (
        <FormikSelectField
          name="billing_mode"
          label="Billing"
          options={BILLING_OPTIONS[billingKey(billing)]}
          helperText="Prepaid jobs draw on the customer’s activated hours for this machine."
        />
      )}
      <FormControl>
        <FormLabel id="rate-mode-label">Hourly rate source</FormLabel>
        <RadioGroup
          row
          aria-labelledby="rate-mode-label"
          value={values.rate_mode}
          onChange={(e) => {
            void setFieldValue('rate_mode', e.target.value);
          }}
        >
          <FormControlLabel value="RATE_CARD" control={<Radio />} label="Use the rate card" />
          <FormControlLabel value="NEGOTIATED" control={<Radio />} label="Negotiated rate" />
        </RadioGroup>
      </FormControl>
      {values.rate_mode === 'RATE_CARD' ? (
        <Alert severity="info">
          The hourly rate (and minimum hours, unless entered below) come from your rate card for the
          machine&apos;s category, effective at the planned start. The price is snapshotted on the
          job.
        </Alert>
      ) : (
        <Typography variant="body2" color="text.secondary">
          A negotiated rate overrides the rate card for this job only.
        </Typography>
      )}
      <Box className={grid}>
        {values.rate_mode === 'NEGOTIATED' && (
          <FormikTextField
            name="hourly_rate"
            label="Negotiated hourly rate"
            required
            slotProps={decimal}
          />
        )}
        <FormikTextField
          name="minimum_hours"
          label="Minimum hours"
          helperText={
            values.rate_mode === 'RATE_CARD'
              ? 'Empty = the rate card minimum'
              : 'Empty = no minimum'
          }
          slotProps={decimal}
        />
        <FormikSelectField
          name="standby_treatment"
          label="Standby treatment"
          options={STANDBY_OPTIONS}
          required
        />
        {values.standby_treatment === 'STANDBY_RATE' && (
          <FormikTextField
            name="standby_rate"
            label="Standby rate (per hour)"
            required
            slotProps={decimal}
          />
        )}
        <FormikTextField
          name="mobilization_fee"
          label="Mobilization fee"
          required
          slotProps={decimal}
        />
        <FormikTextField
          name="discount_percent"
          label="Discount (%)"
          required
          slotProps={decimal}
        />
        <FormikTextField
          name="tax_rate_percent"
          label="Tax rate (%)"
          required
          slotProps={decimal}
        />
      </Box>
    </>
  );
}
