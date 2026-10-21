import { Alert } from '@mui/material';
import { object } from 'yup';
import { platformPaymentService } from '../../../api/services/platformPaymentService';
import type { PaymentDecisionIn, PaymentDto } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatMoney } from '../../../utils/money';
import { reasonField } from '../shared/validators';

const schema = object({ note: reasonField('Note') });

interface PaymentDecisionDialogProps {
  payment: PaymentDto;
  verified: boolean;
  onClose: () => void;
  onDecided: (payment: PaymentDto) => void;
}

/** Verify (counts towards the invoice balance) or reject a recorded payment, with a note. */
export function PaymentDecisionDialog({
  payment,
  verified,
  onClose,
  onDecided,
}: PaymentDecisionDialogProps) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog
      open
      title={verified ? 'Verify payment' : 'Reject payment'}
      initialValues={{ note: '' }}
      validationSchema={schema}
      submitLabel={verified ? 'Verify' : 'Reject'}
      onClose={onClose}
      onSubmit={async (v) => {
        const body: PaymentDecisionIn = { verified, note: v.note.trim() };
        onDecided(await platformPaymentService.decide(payment.id, body, keyFor(body)));
      }}
    >
      <Alert severity={verified ? 'info' : 'warning'}>
        {formatMoney(payment.amount, payment.currency)} · ref {payment.reference}.{' '}
        {verified
          ? 'Verifying applies the payment to the invoice balance.'
          : 'A rejected payment never affects the invoice balance.'}
      </Alert>
      <FormikTextField name="note" label="Note" required multiline minRows={2} />
    </FormDialog>
  );
}
