import { Alert } from '@mui/material';
import { useState } from 'react';
import { object } from 'yup';
import { platformInvoiceService } from '../../../api/services/platformInvoiceService';
import type { CreditAdjustmentIn, InvoiceDto } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { compareDecimal, formatMoney, isDecimalString } from '../../../utils/money';
import { positiveDecimalField, reasonField } from '../shared/validators';

interface ApplyCreditDialogProps {
  invoice: InvoiceDto & { id: string };
  onClose: () => void;
  onApplied: (invoice: InvoiceDto) => void;
}

/** Audited credit adjustment against an issued invoice (never edits its lines). */
export function ApplyCreditDialog({ invoice, onClose, onApplied }: ApplyCreditDialogProps) {
  const keyFor = useIdempotencyKey();
  const [schema] = useState(() =>
    object({
      amount: positiveDecimalField('Amount').test(
        'not-over-balance',
        'Credit cannot exceed the outstanding balance',
        (v) => !isDecimalString(v) || compareDecimal(v, invoice.balance) <= 0,
      ),
      reason: reasonField(),
    }),
  );
  return (
    <FormDialog
      open
      title={`Apply credit · ${invoice.invoice_number ?? ''}`}
      initialValues={{ amount: '', reason: '' }}
      validationSchema={schema}
      submitLabel="Apply credit"
      onClose={onClose}
      onSubmit={async (v) => {
        const payload: CreditAdjustmentIn = {
          invoice_id: invoice.id,
          amount: v.amount.trim(),
          reason: v.reason.trim(),
        };
        onApplied(await platformInvoiceService.applyCredit(payload, keyFor(payload)));
      }}
    >
      <Alert severity="info">
        Outstanding balance {formatMoney(invoice.balance, invoice.currency)}.
      </Alert>
      <FormikTextField
        name="amount"
        label={`Credit amount (${invoice.currency})`}
        required
        slotProps={{ htmlInput: { inputMode: 'decimal' } }}
      />
      <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
    </FormDialog>
  );
}
