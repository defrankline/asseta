import { Box } from '@mui/material';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import type { FormStep } from '../../../components/forms/StepperFormDialog';
import { CONTACT_FIELDS, CUSTOMER_FIELDS, type CustomerFormValues } from './customerForm';

const grid = 'grid grid-cols-1 gap-4 sm:grid-cols-2';

/** Customer → Contact steps, shared by the create and edit dialogs. */
export const CUSTOMER_STEPS: readonly FormStep<CustomerFormValues>[] = [
  {
    label: 'Customer',
    fields: CUSTOMER_FIELDS,
    render: () => (
      <Box className={grid}>
        <FormikTextField name="code" label="Code" required />
        <FormikTextField name="name" label="Name" required />
        <FormikTextField name="tax_id" label="Tax ID" />
        <FormikTextField
          name="payment_terms_days"
          label="Payment terms (days)"
          required
          slotProps={{ htmlInput: { inputMode: 'numeric' } }}
        />
      </Box>
    ),
  },
  {
    label: 'Contact',
    fields: CONTACT_FIELDS,
    render: () => (
      <Box className={grid}>
        <FormikTextField name="contact_name" label="Contact name" />
        <FormikTextField name="contact_phone" label="Contact phone" />
        <FormikTextField name="contact_email" label="Contact email" />
      </Box>
    ),
  },
];
