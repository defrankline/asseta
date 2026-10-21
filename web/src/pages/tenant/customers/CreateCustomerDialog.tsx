import { useState } from 'react';
import { customerService } from '../../../api/services/customerService';
import type { CustomerDto } from '../../../api/types';
import { StepperFormDialog } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import {
  customerFormSchema,
  emptyCustomerValues,
  toCustomerPayload,
  type CustomerFormValues,
} from './customerForm';
import { CUSTOMER_STEPS } from './customerSteps';
import { CustomerReview } from './CustomerViews';

interface CreateCustomerDialogProps {
  onClose: () => void;
  onCreated: (customer: CustomerDto) => void;
}

/** Customer → Contact → Review. Mount only while open. */
export function CreateCustomerDialog({ onClose, onCreated }: CreateCustomerDialogProps) {
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState(emptyCustomerValues);
  return (
    <StepperFormDialog<CustomerFormValues>
      open
      title="New customer"
      steps={CUSTOMER_STEPS}
      initialValues={initialValues}
      validationSchema={customerFormSchema}
      submitLabel="Create customer"
      renderReview={(v) => <CustomerReview values={v} />}
      onClose={onClose}
      onSubmit={async (values) => {
        const payload = toCustomerPayload(values);
        onCreated(await customerService.create(payload, keyFor(payload)));
      }}
    />
  );
}
