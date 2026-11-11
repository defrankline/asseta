import { FormControlLabel, Stack, Switch, Typography } from '@mui/material';
import { useFormikContext } from 'formik';
import type { FieldContractDto } from '../../../api/types';
import { FormikDateTimeField } from '../../../components/forms/FormikDateTimeField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { FormikJobSitePicker } from '../shared/lookupPickers';
import { FormikCustomerContractPicker } from './hoursPickers';
import type { PurchaseValues } from './purchaseForm';

/** Optional: book the job together with the sale (a field job request billed from these hours). */
export function BookJobSection({
  timeZone,
  siteVisible,
  onContract,
}: {
  timeZone: string;
  siteVisible: boolean;
  onContract: (c: FieldContractDto | null) => void;
}) {
  const { values, setFieldValue } = useFormikContext<PurchaseValues>();
  const existing = values.customer_mode === 'EXISTING' && values.customer_id !== '';
  return (
    <Stack spacing={1.5} sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5 }}>
      <FormControlLabel
        control={
          <Switch
            checked={values.book_job}
            onChange={(e) => {
              void setFieldValue('book_job', e.target.checked);
            }}
          />
        }
        label="Book the job"
      />
      {values.book_job ? (
        <>
          <FormikDateTimeField name="job_start" label="Job starts" timeZone={timeZone} required />
          <FormikDateTimeField
            name="job_end"
            label="Job ends (optional)"
            timeZone={timeZone}
            helperText="Leave empty when the end is not known yet."
          />
          {siteVisible && (
            <FormikJobSitePicker
              name="booking_site_id"
              label="Site of the job (optional)"
              helperText="Leave empty to use the sale's site, then the contract's site."
            />
          )}
          {existing ? (
            <FormikCustomerContractPicker
              key={values.customer_id}
              customerId={values.customer_id}
              name="job_contract_id"
              label="Contract (optional)"
              helperText="Leave empty to use the customer's contract"
              onOptionChange={onContract}
            />
          ) : (
            values.customer_mode === 'WALK_IN' && (
              <Typography variant="body2" color="text.secondary">
                The job goes on the walk-in customer's contract, as your company policy sets.
              </Typography>
            )
          )}
          <FormikTextField name="job_note" label="Job note (optional)" multiline minRows={2} />
          <Typography variant="body2" color="text.secondary">
            The job is requested with the sale and waits for approval like any field request.
          </Typography>
        </>
      ) : (
        <Typography variant="body2" color="text.secondary">
          Switch on to request the job together with the sale.
        </Typography>
      )}
    </Stack>
  );
}
