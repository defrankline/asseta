import { Alert } from '@mui/material';
import { useFormikContext } from 'formik';
import { useEffect, useMemo, useRef, useState } from 'react';
import { CAPABILITY, useCapabilityEnabled } from '../../../access/capabilities';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { newUuid } from '../../../api/ids';
import { cashService } from '../../../api/services/cashService';
import { customerService } from '../../../api/services/customerService';
import { jobService } from '../../../api/services/jobService';
import type { CustomerDto, CustomerPaymentDto, HireInvoiceDto } from '../../../api/types';
import type { CustodianDto } from '../../../api/custodyTypes';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { FormikDateTimeField } from '../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useSession } from '../../../session/useSession';
import { formatEnteredMoney } from '../../../utils/money';
import { formatInstantIn } from '../../../utils/time';
import { withErrorCode } from '../shared/errorHints';
import { CURRENCY_OPTIONS, FINANCE_ERROR_HINTS } from '../shared/financeDisplay';
import { FormikCustodianIdPicker } from '../finance/cash/custodyPickers';
import {
  customerOptionLabel,
  invoiceOptionLabel,
  searchIssuedInvoices,
} from '../shared/financeLookups';
import { FormikCustomerIdPicker } from '../shared/financePickers';
import { optionId } from '../shared/lookups';
import { useCashPolicy } from '../finance/cash/custodyHooks';
import { FormikPurchaseIdPicker } from '../hours/hoursPickers';
import {
  emptyCollectionValues,
  fieldCollectionSchemaFor,
  toFieldCollectionPayload,
  type FieldCollectionValues,
} from './fieldCash';
import { FormikFieldJobIdPicker } from './fieldPickers';

/** A purchase or invoice belongs to one customer: changing the customer clears the choice. */
function ClearLinksOnCustomerChange({ customerId }: { customerId: string }) {
  const { setFieldValue } = useFormikContext<FieldCollectionValues>();
  const previous = useRef(customerId);
  useEffect(() => {
    if (previous.current !== customerId) {
      previous.current = customerId;
      void setFieldValue('purchase_id', '');
      void setFieldValue('invoice_id', '');
    }
  }, [customerId, setFieldValue]);
  return null;
}

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
  /** The tenant lets recorders collect into another custodian's custody (no login needed). */
  forOthers?: boolean;
  onClose: () => void;
  onRecorded: (payment: CustomerPaymentDto) => void;
}

/** Collection → Details → Review. Cash enters the caller's custody as CLAIMED until verified. */
export function FieldCollectionDialog({
  timeZone,
  forOthers = false,
  onClose,
  onRecorded,
}: FieldCollectionDialogProps) {
  const keyFor = useIdempotencyKey();
  const [clientId] = useState(newUuid);
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [custodian, setCustodian] = useState<CustodianDto | null>(null);
  const [initial] = useState(() => emptyCollectionValues(new Date().toISOString()));
  const [invoice, setInvoice] = useState<HireInvoiceDto | null>(null);
  const { hasPermission } = useSession();
  const canSearchInvoices = hasPermission(PERMISSIONS.tenantFinanceRead);
  const canSearchPurchases = hasPermission(
    [PERMISSIONS.tenantHoursPurchase, PERMISSIONS.tenantHoursRead],
    'any',
  );
  const controlsOn = useCapabilityEnabled(CAPABILITY.cashCustody);
  const policy = useCashPolicy();
  const linkRequired = controlsOn && (policy?.collectionLinkRequired ?? false);
  const schema = useMemo(() => fieldCollectionSchemaFor(linkRequired), [linkRequired]);
  return (
    <StepperFormDialog<FieldCollectionValues>
      open
      title="Record cash collection"
      initialValues={initial}
      validationSchema={schema}
      submitLabel="Record collection"
      onClose={onClose}
      steps={[
        {
          label: 'Collection',
          fields: [
            'job_id',
            'customer_id',
            'staff_member_id',
            'amount',
            'currency',
            'purchase_id',
            'invoice_id',
          ],
          render: (f) => (
            <>
              <JobCustomerSync />
              {forOthers && (
                <FormikCustodianIdPicker
                  name="staff_member_id"
                  label="Collected by (custodian)"
                  helperText="Leave empty when the cash is in your own custody."
                  onOptionChange={setCustodian}
                />
              )}
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
              <ClearLinksOnCustomerChange customerId={f.values.customer_id} />
              {canSearchPurchases && (
                <FormikPurchaseIdPicker
                  key={`purchase-${f.values.customer_id}`}
                  name="purchase_id"
                  label={linkRequired ? 'Hours purchase it pays for' : 'Hours purchase (optional)'}
                  customerId={f.values.customer_id}
                  disabled={f.values.customer_id === ''}
                  helperText="Linked up to its open amount; the rest stays as customer credit."
                />
              )}
              {canSearchInvoices && (
                <FormikAsyncIdAutocomplete<HireInvoiceDto>
                  key={`invoice-${f.values.customer_id}`}
                  name="invoice_id"
                  label={linkRequired ? 'Or the invoice it pays' : 'Invoice (optional)'}
                  disabled={f.values.customer_id === ''}
                  fetchOptions={searchIssuedInvoices(f.values.customer_id)}
                  getOptionId={optionId}
                  getOptionLabel={invoiceOptionLabel}
                  onOptionChange={setInvoice}
                  noOptionsText="No issued invoice of this customer matches"
                />
              )}
              {linkRequired && f.submitCount > 0 && f.errors.purchase_id !== undefined && (
                <Alert severity="error">{f.errors.purchase_id}</Alert>
              )}
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
              { label: 'Custodian', value: custodian?.full_name ?? 'Me (my custody)' },
            ]}
          />
          <Alert severity="info">
            Recorded as CLAIMED in the custodian’s cash custody. The office verifies it and
            allocates it to the customer’s invoices; until then it does not reduce the customer’s
            balance.
          </Alert>
        </>
      )}
      onSubmit={async (v) => {
        const body = toFieldCollectionPayload(v, clientId, v.invoice_id === '' ? null : invoice);
        try {
          onRecorded(await cashService.recordCollection(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, FINANCE_ERROR_HINTS);
        }
      }}
    />
  );
}
