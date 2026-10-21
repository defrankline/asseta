import { Box } from '@mui/material';
import { useState } from 'react';
import { customerService } from '../../../api/services/customerService';
import type { CustomerDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import {
  CONTACT_FIELDS,
  CUSTOMER_FIELDS,
  customerFormSchema,
  emptyCustomerValues,
  toCustomerPayload,
  type CustomerFormValues,
} from './customerForm';

const grid = 'grid grid-cols-1 gap-4 sm:grid-cols-2';

interface CreateCustomerDialogProps {
  onClose: () => void;
  onCreated: (customer: CustomerDto) => void;
}

/** Customer → Contact → Review. Mount only while open. */
export function CreateCustomerDialog({ onClose, onCreated }: CreateCustomerDialogProps) {
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState(emptyCustomerValues);
  const steps: FormStep<CustomerFormValues>[] = [
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
  return (
    <StepperFormDialog<CustomerFormValues>
      open
      title="New customer"
      steps={steps}
      initialValues={initialValues}
      validationSchema={customerFormSchema}
      submitLabel="Create customer"
      renderReview={(v) => (
        <KeyValueGrid
          columns={2}
          items={[
            { label: 'Code', value: v.code.trim() },
            { label: 'Name', value: v.name.trim() },
            { label: 'Tax ID', value: v.tax_id.trim() || '—' },
            { label: 'Payment terms', value: `${v.payment_terms_days} days` },
            { label: 'Contact', value: v.contact_name.trim() || '—' },
            { label: 'Phone', value: v.contact_phone.trim() || '—' },
            { label: 'Email', value: v.contact_email.trim() || '—' },
          ]}
        />
      )}
      onClose={onClose}
      onSubmit={async (values) => {
        const payload = toCustomerPayload(values);
        onCreated(await customerService.create(payload, keyFor(payload)));
      }}
    />
  );
}
