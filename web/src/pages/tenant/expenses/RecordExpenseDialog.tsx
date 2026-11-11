import { Alert, Typography } from '@mui/material';
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
import { formatEnteredMoney } from '../../../utils/money';
import { formatInstantIn } from '../../../utils/time';
import { withErrorCode } from '../shared/errorHints';
import {
  CURRENCY_OPTIONS,
  FINANCE_ERROR_HINTS,
  PAID_FROM_CHOICES,
  PAID_FROM_LABELS,
} from '../shared/financeDisplay';
import { FormikAdvanceIdPicker, FormikFundIdPicker } from '../finance/pettyCash/pettyCashPickers';
import { usePettyCashOn, usePettyCashPolicy } from '../finance/pettyCash/pettyCashState';
import { expenseCategoryOptionLabel } from '../shared/financeLookups';
import {
  FormikExpenseCategoryIdPicker,
  FormikJobIdPicker,
  FormikMachineIdPicker,
  FormikStaffIdPicker,
} from '../shared/financePickers';
import { FormikFieldJobIdPicker, FormikFieldMachineIdPicker } from '../field/fieldPickers';
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
  /**
   * `field`: a supervisor's own expense (Field work) — jobs and machines they work on, paid from
   * their own custody when cash. `office` (default) may name any custodian.
   */
  variant?: 'office' | 'field';
  /** Pre-selects the job (Field work job workspace). */
  jobId?: string;
  /** Pre-selects "paid from" this petty cash fund (the holder's petty cash page). */
  pettyCashFundId?: string;
  timeZone: string;
  onClose: () => void;
  onRecorded: (expense: ExpenseDto) => void;
}

/** Expense → Attribution & payment → Receipts & GPS → Review (console capture). */
export function RecordExpenseDialog({
  variant = 'office',
  jobId,
  pettyCashFundId,
  timeZone,
  onClose,
  onRecorded,
}: RecordExpenseDialogProps) {
  const pettyOn = usePettyCashOn();
  const pettyPolicy = usePettyCashPolicy();
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(() => newUuid());
  const [category, setCategory] = useState<ExpenseCategoryDto | null>(null);
  const [initial] = useState(() => ({
    ...emptyExpenseValues(new Date().toISOString()),
    job_id: jobId ?? '',
    ...(pettyCashFundId === undefined
      ? {}
      : { paid_from: 'PETTY_CASH' as const, petty_cash_fund_id: pettyCashFundId }),
  }));
  const field = variant === 'field';
  const JobPicker = field ? FormikFieldJobIdPicker : FormikJobIdPicker;
  const MachinePicker = field ? FormikFieldMachineIdPicker : FormikMachineIdPicker;
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
          <JobPicker
            name="job_id"
            label="Job (optional)"
            helperText="Attributes the cost to the job and its machine."
          />
          <MachinePicker
            name="machine_id"
            label="Machine (optional)"
            helperText="Leave empty when a job is chosen; it must match the job's machine."
          />
          <FormikSelectField
            name="paid_from"
            label="Paid from"
            options={PAID_FROM_CHOICES[pettyOn ? 'petty' : 'basic']}
            required
          />
          {formik.values.paid_from === 'PETTY_CASH' && (
            <>
              <FormikFundIdPicker
                name="petty_cash_fund_id"
                label="Petty cash fund"
                required
                helperText="The expense must be in the fund's currency. Spending more than the fund has available is refused."
              />
              {pettyPolicy?.advancesEnabled === true && (
                <FormikAdvanceIdPicker
                  name="petty_cash_advance_id"
                  label="Paid from an advance (optional)"
                  fundId={formik.values.petty_cash_fund_id}
                />
              )}
            </>
          )}
          {formik.values.paid_from === 'CASH_CUSTODY' && field && (
            <Typography variant="body2" color="text.secondary">
              Paid from your own cash custody. An approved cash expense reduces your outstanding
              cash.
            </Typography>
          )}
          {formik.values.paid_from === 'CASH_CUSTODY' && !field && (
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
              { label: 'Amount', value: formatEnteredMoney(v.amount, v.currency) },
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
