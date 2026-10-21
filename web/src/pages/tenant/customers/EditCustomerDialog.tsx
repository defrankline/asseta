import { Stack } from '@mui/material';
import { useState } from 'react';
import { withErrorCode } from '../../../api/lifecycle';
import { customerService } from '../../../api/services/customerService';
import type { CustomerDto } from '../../../api/types';
import { StepperFormDialog } from '../../../components/forms/StepperFormDialog';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { CUSTOMER_ERROR_HINTS } from './customerLifecycle';
import {
  customerFormSchema,
  toCustomerUpdatePayload,
  valuesFromCustomer,
  type CustomerFormValues,
} from './customerForm';
import { CUSTOMER_STEPS } from './customerSteps';
import { CustomerReview } from './CustomerViews';

interface EditCustomerDialogProps {
  customer: CustomerDto;
  onClose: () => void;
  onSaved: (customer: CustomerDto) => void;
  /** STALE_VERSION: the user asked to reload the latest record. */
  onReload: () => void;
}

/** Edit a customer (PUT with the `version` read). Mount only while open. */
export function EditCustomerDialog({
  customer,
  onClose,
  onSaved,
  onReload,
}: EditCustomerDialogProps) {
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState(() => valuesFromCustomer(customer));
  const { stale, guard } = useStaleVersion();
  return (
    <StepperFormDialog<CustomerFormValues>
      open
      title={`Edit customer ${customer.code}`}
      steps={CUSTOMER_STEPS}
      initialValues={initialValues}
      validationSchema={customerFormSchema}
      submitLabel="Save changes"
      renderReview={(v) => (
        <Stack spacing={2}>
          {stale && (
            <StaleVersionAlert
              onReload={() => {
                onReload();
                onClose();
              }}
            />
          )}
          <CustomerReview values={v} />
        </Stack>
      )}
      onClose={onClose}
      onSubmit={async (values) => {
        const payload = toCustomerUpdatePayload(values, customer.version);
        try {
          onSaved(await guard(() => customerService.update(customer.id, payload, keyFor(payload))));
        } catch (err) {
          throw withErrorCode(err, CUSTOMER_ERROR_HINTS);
        }
      }}
    />
  );
}
