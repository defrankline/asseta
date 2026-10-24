import { Alert } from '@mui/material';
import { useFormikContext } from 'formik';
import { useEffect, useState } from 'react';
import { newUuid } from '../../../api/ids';
import { cashService } from '../../../api/services/cashService';
import { customerService } from '../../../api/services/customerService';
import { jobService } from '../../../api/services/jobService';
import type { CustomerDto, CustomerPaymentDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikDateTimeField } from '../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatEnteredMoney } from '../../../utils/money';
import { formatInstantIn } from '../../../utils/time';
import { withErrorCode } from '../shared/errorHints';
import { CURRENCY_OPTIONS, FINANCE_ERROR_HINTS } from '../shared/financeDisplay';
import { customerOptionLabel } from '../shared/financeLookups';
import { FormikCustomerIdPicker } from '../shared/financePickers';
import {
  emptyCollectionValues,
  fieldCollectionSchema,
  toFieldCollectionPayload,
  type FieldCollectionValues,
} from './fieldCash';
import { FormikFieldJobIdPicker } from './fieldPickers';

/** Picking a job fills the customer of its contract (the customer stays editable). */
function JobCustomerSync() {
  const { values, setFieldValue } = useFormikContext<FieldCollectionValues>();
  const jobId = values.job_id;
  useEffect(() => {
    if (jobId === '') return undefined;
    const controller = new AbortController();
    jobService
      .summary(jobId, controller.signal)
      .then((s) => customerService.getContract(s.job.contract_id, controller.signal))
      .then((contract) => {
        if (!controller.signal.aborted) void setFieldValue('customer_id', contract.customer_id);
      })
      .catch(() => {
        // The customer can still be chosen by hand.
      });
    return () => {
      controller.abort();
    };
  }, [jobId, setFieldValue]);
  return null;
}

interface FieldCollectionDialogProps {
  timeZone: string;
  onClose: () => void;
  onRecorded: (payment: CustomerPaymentDto) => void;
}

/** Collection → Details → Review. Cash enters the caller's custody as CLAIMED until verified. */
export function FieldCollectionDialog({
  timeZone,
  onClose,
  onRecorded,
}: FieldCollectionDialogProps) {
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(newUuid);
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [initial] = useState(() => emptyCollectionValues(new Date().toISOString()));
  return (
    <StepperFormDialog<FieldCollectionValues>
      open
      title="Record cash collection"
      initialValues={initial}
      validationSchema={fieldCollectionSchema}
      submitLabel="Record collection"
      onClose={onClose}
      steps={[
        {
          label: 'Collection',
          fields: ['job_id', 'customer_id', 'amount', 'currency'],
          render: () => (
            <>
              <JobCustomerSync />
              <FormikFieldJobIdPicker
                name="job_id"
                label="Job (optional)"
                helperText="Fills in the job's customer."
              />
              <FormikCustomerIdPicker
                name="customer_id"
                label="Customer"
                required
                onOptionChange={setCustomer}
              />
              <FormikTextField
                name="amount"
                label="Amount received"
                required
                slotProps={{ htmlInput: { inputMode: 'decimal' } }}
              />
              <FormikSelectField name="currency" label="Currency" options={CURRENCY_OPTIONS} />
            </>
          ),
        },
        {
          label: 'Details',
          fields: ['received_at', 'reference', 'note'],
          render: () => (
            <>
              <FormikDateTimeField
                name="received_at"
                label="Received at"
                timeZone={timeZone}
                required
              />
              <FormikTextField name="reference" label="Reference (optional, e.g. receipt number)" />
              <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
            </>
          ),
        },
      ]}
      renderReview={(v) => (
        <>
          <KeyValueGrid
            columns={2}
            items={[
              {
                label: 'Customer',
                value: customer === null ? v.customer_id : customerOptionLabel(customer),
              },
              { label: 'Amount', value: formatEnteredMoney(v.amount, v.currency) },
              { label: 'Received at', value: formatInstantIn(v.received_at, timeZone) },
              { label: 'Reference', value: v.reference.trim() || '—' },
              { label: 'Custodian', value: 'Me (my custody)' },
            ]}
          />
          <Alert severity="info">
            Recorded as CLAIMED in your cash custody. The office verifies it and allocates it to the
            customer’s invoices; until then it does not reduce the customer’s balance.
          </Alert>
        </>
      )}
      onSubmit={async (v) => {
        const body = toFieldCollectionPayload(v, clientId);
        try {
          onRecorded(await cashService.recordCollection(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, FINANCE_ERROR_HINTS);
        }
      }}
    />
  );
}
