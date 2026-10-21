import { Alert } from '@mui/material';
import { useState } from 'react';
import { object } from 'yup';
import { subscriptionService } from '../../../api/services/subscriptionService';
import type { GenerateInvoicesDto } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikDateField } from '../../../components/forms/FormikDateField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { todayIsoDate } from '../../../utils/dates';
import { isoDateField } from '../shared/validators';

interface GenerateInvoicesDialogProps {
  subscriptionId: string;
  onClose: () => void;
  onGenerated: (result: GenerateInvoicesDto) => void;
}

/** Issue all due invoices up to an as-of date; existing periods are reported, never re-issued. */
export function GenerateInvoicesDialog({
  subscriptionId,
  onClose,
  onGenerated,
}: GenerateInvoicesDialogProps) {
  const keyFor = useIdempotencyKey();
  const today = todayIsoDate();
  const [schema] = useState(() =>
    object({
      as_of: isoDateField('As of').test(
        'not-future',
        'As-of date cannot be in the future',
        (v) => v <= today,
      ),
    }),
  );
  return (
    <FormDialog
      open
      title="Generate due invoices"
      initialValues={{ as_of: today }}
      validationSchema={schema}
      submitLabel="Generate"
      onClose={onClose}
      onSubmit={async (v) => {
        onGenerated(await subscriptionService.generateInvoices(subscriptionId, v.as_of, keyFor(v)));
      }}
    >
      <Alert severity="info">
        Generation is idempotent per period: periods already invoiced are skipped and missed periods
        are caught up. Issued lines are immutable.
      </Alert>
      <FormikDateField name="as_of" label="As of" required maxDate={today} />
    </FormDialog>
  );
}
