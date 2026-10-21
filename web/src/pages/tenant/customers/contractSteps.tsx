import { Box } from '@mui/material';
import type { JobSiteDto } from '../../../api/types';
import { FormikDateTimeField } from '../../../components/forms/FormikDateTimeField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import type { FormStep } from '../../../components/forms/StepperFormDialog';
import { FormikJobSitePicker } from '../shared/lookupPickers';
import { CONTRACT_FIELDS, PERIOD_FIELDS, type ContractFormValues } from './contractForm';

interface StepOptions {
  timeZone: string;
  /** Show the job-site picker (needs `tenant.geofence.read`). */
  canPickSite: boolean;
  onSiteChange: (site: JobSiteDto | null) => void;
}

/** Contract → Period steps, shared by the create and edit dialogs. */
export function contractSteps({
  timeZone,
  canPickSite,
  onSiteChange,
}: StepOptions): FormStep<ContractFormValues>[] {
  return [
    {
      label: 'Contract',
      fields: CONTRACT_FIELDS,
      render: () => (
        <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormikTextField name="contract_number" label="Contract number" required />
          <FormikTextField name="reference" label="Customer reference" />
          {canPickSite && (
            <FormikJobSitePicker
              name="job_site_id"
              label="Default job site"
              helperText="Jobs under this contract default to this site"
              onOptionChange={onSiteChange}
            />
          )}
        </Box>
      ),
    },
    {
      label: 'Period',
      fields: PERIOD_FIELDS,
      render: () => (
        <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormikDateTimeField name="starts_on" label="Starts" timeZone={timeZone} required />
          <FormikDateTimeField
            name="ends_on"
            label="Ends (optional)"
            timeZone={timeZone}
            helperText="Leave empty for an open-ended contract"
          />
          <Box className="sm:col-span-2">
            <FormikTextField name="notes" label="Notes" multiline minRows={2} />
          </Box>
        </Box>
      ),
    },
  ];
}
