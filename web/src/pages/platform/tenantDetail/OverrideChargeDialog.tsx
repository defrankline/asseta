import { Alert } from '@mui/material';
import { object } from 'yup';
import { subscriptionService } from '../../../api/services/subscriptionService';
import type { OverridePendingChargeIn, PendingChargeDto } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatMoney } from '../../../utils/money';
import { reasonField, signedDecimalField } from '../shared/validators';

const schema = object({ amount: signedDecimalField('Amount'), reason: reasonField() });

interface OverrideChargeDialogProps {
  charge: PendingChargeDto;
  currency: string;
  onClose: () => void;
  onOverridden: (charge: PendingChargeDto) => void;
}

/** Audited override of a pending (not yet invoiced) proration amount. */
export function OverrideChargeDialog({
  charge,
  currency,
  onClose,
  onOverridden,
}: OverrideChargeDialogProps) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog
      open
      title="Override pending charge"
      initialValues={{ amount: charge.amount, reason: '' }}
      validationSchema={schema}
      submitLabel="Override"
      onClose={onClose}
      onSubmit={async (v) => {
        const body: OverridePendingChargeIn = { amount: v.amount.trim(), reason: v.reason.trim() };
        onOverridden(
          await subscriptionService.overridePendingCharge(charge.id, body, keyFor(body)),
        );
      }}
    >
      <Alert severity="info">
        Computed amount {formatMoney(charge.computed_amount, currency)}. {charge.explanation}{' '}
        Credits are negative amounts.
      </Alert>
      <FormikTextField
        name="amount"
        label={`Amount (${currency})`}
        required
        slotProps={{ htmlInput: { inputMode: 'decimal' } }}
      />
      <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
    </FormDialog>
  );
}
