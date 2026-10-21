import { Alert } from '@mui/material';
import { useState } from 'react';
import { newUuid } from '../../../api/ids';
import { expenseService } from '../../../api/services/expenseService';
import type { ExpenseCategoryDto, ExpenseDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikDateTimeField } from '../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../utils/time';
import { withErrorCode } from '../shared/errorHints';
import {
  CURRENCY_OPTIONS,
  FINANCE_ERROR_HINTS,
  PAID_FROM_LABELS,
  PAID_FROM_OPTIONS,
} from '../shared/financeDisplay';
import { expenseCategoryOptionLabel } from '../shared/financeLookups';
import {
  FormikExpenseCategoryIdPicker,
  FormikJobIdPicker,
  FormikMachineIdPicker,
  FormikStaffIdPicker,
} from '../shared/financePickers';
import { ExpenseEvidenceStep } from './ExpenseEvidenceStep';
import {
  ATTRIBUTION_FIELDS,
  emptyExpenseValues,
  EVIDENCE_FIELDS,
  EXPENSE_FIELDS,
  expenseFormSchema,
  toExpensePayload,
  type ExpenseFormValues,
} from './expenseForm';

interface RecordExpenseDialogProps {
  timeZone: string;
  onClose: () => void;
  onRecorded: (expense: ExpenseDto) => void;
}

/** Expense → Attribution & payment → Receipts & GPS → Review (console capture). */
export function RecordExpenseDialog({ timeZone, onClose, onRecorded }: RecordExpenseDialogProps) {
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(() => newUuid());
  const [category, setCategory] = useState<ExpenseCategoryDto | null>(null);
  const [initial] = useState(() => emptyExpenseValues(new Date().toISOString()));
  const steps: FormStep<ExpenseFormValues>[] = [
    {
      label: 'Expense',
      fields: EXPENSE_FIELDS,
      render: () => (
        <>
          <FormikExpenseCategoryIdPicker
            name="category_id"
            label="Category"
            required
            onOptionChange={setCategory}
          />
          <FormikTextField name="description" label="Description" required multiline minRows={2} />
          <FormikTextField name="amount" label="Amount" required />
          <FormikSelectField name="currency" label="Currency" options={CURRENCY_OPTIONS} />
          <FormikDateTimeField
            name="incurred_at"
            label="Incurred at"
            timeZone={timeZone}
            required
          />
          <FormikTextField name="supplier" label="Supplier (optional)" />
        </>
      ),
    },
    {
      label: 'Attribution & payment',
      fields: ATTRIBUTION_FIELDS,
      render: (formik) => (
        <>
          <FormikJobIdPicker
            name="job_id"
            label="Job (optional)"
            helperText="Attributes the cost to the job and its machine."
          />
          <FormikMachineIdPicker
            name="machine_id"
            label="Machine (optional)"
            helperText="Leave empty when a job is chosen; it must match the job's machine."
          />
          <FormikSelectField
            name="paid_from"
            label="Paid from"
            options={PAID_FROM_OPTIONS}
            required
          />
          {formik.values.paid_from === 'CASH_CUSTODY' && (
            <FormikStaffIdPicker
              name="custodian_staff_id"
              label="Custodian (whose cash paid)"
              supervisorsOnly
              helperText="Leave empty for your own custody. Approved cash expenses reduce the custodian's outstanding cash."
            />
          )}
        </>
      ),
    },
    { label: 'Receipts & GPS', fields: EVIDENCE_FIELDS, render: () => <ExpenseEvidenceStep /> },
  ];
  return (
    <StepperFormDialog<ExpenseFormValues>
      open
      title="Record expense"
      steps={steps}
      initialValues={initial}
      validationSchema={expenseFormSchema}
      submitLabel="Submit expense"
      onClose={onClose}
      renderReview={(v) => (
        <>
          <KeyValueGrid
            columns={2}
            items={[
              {
                label: 'Category',
                value: category === null ? v.category_id : expenseCategoryOptionLabel(category),
              },
              { label: 'Description', value: v.description.trim() },
              { label: 'Amount', value: `${v.amount} ${v.currency || '(tenant base currency)'}` },
              { label: 'Incurred at', value: formatInstantIn(v.incurred_at, timeZone) },
              { label: 'Paid from', value: PAID_FROM_LABELS[v.paid_from] },
              {
                label: 'Attributed',
                value: v.job_id !== '' ? 'Job' : v.machine_id !== '' ? 'Machine' : 'Unattributed',
              },
              { label: 'Receipts', value: String(v.receipts.length) },
              { label: 'GPS', value: v.gps === null ? 'Not attempted' : v.gps.status },
            ]}
          />
          <Alert severity="info">
            Within the policy’s auto-approval limit the expense is approved at once; above it, an
            approval request goes to someone other than you. The policy version is stamped on the
            expense. Recorded expenses are not edited later.
          </Alert>
        </>
      )}
      onSubmit={async (v) => {
        const body = toExpensePayload(v, clientId);
        try {
          onRecorded(await expenseService.submit(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, FINANCE_ERROR_HINTS);
        }
      }}
    />
  );
}
