import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { FormikTextField } from '../../../components/forms/FormikTextField';

/** Payment terms are a credit decision: only people who manage customers' contracts and rates change them. */
export function PaymentTermsField() {
  const canSetTerms = useCanMutate(PERMISSIONS.tenantCustomerWrite);
  return (
    <FormikTextField
      name="payment_terms_days"
      label="Payment terms (days)"
      required
      disabled={!canSetTerms}
      {...(canSetTerms ? {} : { helperText: 'Set by the office' })}
      slotProps={{ htmlInput: { inputMode: 'numeric' } }}
    />
  );
}
