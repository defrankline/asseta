import { Alert, Box, Typography } from '@mui/material';
import { useState } from 'react';
import { array, object, string, type ObjectSchema } from 'yup';
import { hireInvoiceService } from '../../../../api/services/financeService';
import type { CustomerDto, HireInvoiceDraftIn, HireInvoiceDto } from '../../../../api/types';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { withErrorCode } from '../../shared/errorHints';
import { FINANCE_ERROR_HINTS } from '../../shared/financeDisplay';
import { customerOptionLabel } from '../../shared/financeLookups';
import { FormikCustomerIdPicker } from '../../shared/financePickers';
import { optionalText, orNull } from '../../shared/formRules';
import { useMachineLabels } from '../../shared/useMachineLabels';
import type { EligibleJob } from './eligibleJobs';
import { EligibleJobsStep } from './EligibleJobsStep';

interface DraftValues {
  customer_id: string;
  notes: string;
  job_ids: string[];
}

const schema: ObjectSchema<DraftValues> = object({
  customer_id: string().required('Choose the customer'),
  notes: optionalText('Notes', 1000),
  job_ids: array(string().required())
    .required()
    .min(1, 'Pick at least one billing-ready job')
    .max(100, 'At most 100 jobs per invoice'),
});

interface CreateInvoiceDialogProps {
  /** Pre-selects the customer (e.g. from the customer page). */
  customerId?: string;
  /** Pre-selects jobs of that customer (e.g. "Create invoice" from the unbilled work list). */
  jobIds?: readonly string[];
  onClose: () => void;
  onCreated: (invoice: HireInvoiceDto) => void;
}

/** Customer → billable COMPLETED jobs → Review. Creates a DRAFT; issuing is a separate step. */
export function CreateInvoiceDialog({
  customerId = '',
  jobIds = [],
  onClose,
  onCreated,
}: CreateInvoiceDialogProps) {
  const keyFor = useIdempotencyKey();
  const machineLabel = useMachineLabels();
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [loaded, setLoaded] = useState<ReadonlyMap<string, EligibleJob>>(new Map());
  const remember = (jobs: EligibleJob[]) => {
    setLoaded((prev) => new Map([...prev, ...jobs.map((j) => [j.job.id, j] as const)]));
  };
  const steps: FormStep<DraftValues>[] = [
    {
      label: 'Customer',
      fields: ['customer_id', 'notes'],
      render: (formik) => (
        <>
          <FormikCustomerIdPicker
            name="customer_id"
            label="Customer"
            required
            onOptionChange={(c) => {
              setCustomer(c);
              // Resolving the pre-selected customer keeps the pre-selected jobs; a new customer clears them.
              const changed = (c?.id ?? '') !== formik.values.customer_id;
              if (changed && formik.values.job_ids.length > 0)
                void formik.setFieldValue('job_ids', []);
            }}
          />
          <FormikTextField name="notes" label="Notes (optional)" multiline minRows={2} />
        </>
      ),
    },
    {
      label: 'Jobs',
      fields: ['job_ids'],
      render: (formik) => (
        <EligibleJobsStep
          customerId={formik.values.customer_id}
          selected={formik.values.job_ids}
          machineLabel={machineLabel}
          onLoaded={remember}
          error={
            formik.touched.job_ids === true && typeof formik.errors.job_ids === 'string'
              ? formik.errors.job_ids
              : undefined
          }
          onChange={(ids) => {
            void formik.setFieldValue('job_ids', ids);
          }}
        />
      ),
    },
  ];
  return (
    <StepperFormDialog<DraftValues>
      open
      title="New hire invoice (draft)"
      steps={steps}
      initialValues={{ customer_id: customerId, notes: '', job_ids: [...jobIds] }}
      validationSchema={schema}
      submitLabel="Create draft"
      maxWidth="lg"
      onClose={onClose}
      renderReview={(v) => (
        <Box className="flex flex-col gap-3">
          <KeyValueGrid
            columns={2}
            items={[
              {
                label: 'Customer',
                value: customer === null ? v.customer_id : customerOptionLabel(customer),
              },
              { label: 'Notes', value: v.notes.trim() || '—' },
            ]}
          />
          <Typography variant="subtitle2">Jobs to invoice</Typography>
          {v.job_ids.map((id) => {
            const e = loaded.get(id);
            return (
              <Box key={id} className="flex justify-between gap-2">
                <span>
                  {e?.job.job_number ?? id} ·{' '}
                  {e === undefined ? '' : machineLabel(e.job.machine_id)}
                </span>
                {e?.summary.charges != null && (
                  <MoneyText
                    amount={e.summary.charges.total}
                    currency={e.summary.charges.currency}
                  />
                )}
              </Box>
            );
          })}
          <Alert severity="info">
            The draft copies these charges as lines; the server computes the totals. Issuing later
            re-checks the charges (DRAFT_STALE if they changed) and assigns the invoice number.
          </Alert>
        </Box>
      )}
      onSubmit={async (v) => {
        const body: HireInvoiceDraftIn = {
          customer_id: v.customer_id,
          job_ids: v.job_ids,
          notes: orNull(v.notes),
        };
        try {
          onCreated(await hireInvoiceService.createDraft(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, FINANCE_ERROR_HINTS);
        }
      }}
    />
  );
}
