import { Alert } from '@mui/material';
import { object, string, type ObjectSchema } from 'yup';
import { hireInvoiceService } from '../../../../api/services/financeService';
import type { HireInvoiceDto, HireInvoiceIssueIn } from '../../../../api/types';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { FormDialog } from '../../../../components/forms/FormDialog';
import { FormikDateField } from '../../../../components/forms/FormikDateField';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { isIsoDate } from '../../../../utils/dates';
import { withErrorCode } from '../../shared/errorHints';
import { FINANCE_ERROR_HINTS } from '../../shared/financeDisplay';

interface IssueValues {
  due_date: string;
}

const schema: ObjectSchema<IssueValues> = object({
  due_date: string()
    .ensure()
    .test('date', 'Enter a valid date', (v) => v === '' || isIsoDate(v)),
});

interface IssueInvoiceDialogProps {
  invoice: HireInvoiceDto;
  onClose: () => void;
  onIssued: (invoice: HireInvoiceDto) => void;
}

/** Issue a draft: the server re-prices its jobs, numbers it and freezes it. Mount only while open. */
export function IssueInvoiceDialog({ invoice, onClose, onIssued }: IssueInvoiceDialogProps) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<IssueValues>
      open
      title="Issue hire invoice"
      initialValues={{ due_date: '' }}
      validationSchema={schema}
      submitLabel="Issue invoice"
      onClose={onClose}
      onSubmit={async (v) => {
        const body: HireInvoiceIssueIn = { due_date: v.due_date === '' ? null : v.due_date };
        try {
          onIssued(await hireInvoiceService.issue(invoice.id, body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, FINANCE_ERROR_HINTS);
        }
      }}
    >
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Lines', value: String(invoice.lines.length) },
          {
            label: 'Total',
            value: <MoneyText amount={invoice.total} currency={invoice.currency} strong />,
          },
        ]}
      />
      <Alert severity="warning">
        Issuing assigns the invoice number and freezes the lines and totals. Issued invoices are
        never edited: a mistake is corrected by voiding (a recorded reversal) and drafting again. If
        job charges changed since drafting, the server refuses with DRAFT_STALE.
      </Alert>
      <FormikDateField
        name="due_date"
        label="Due date (optional)"
        helperText="Defaults to the issue date plus the customer’s payment terms."
      />
    </FormDialog>
  );
}
