import {
  Alert,
  FormControl,
  FormControlLabel,
  FormLabel,
  Radio,
  RadioGroup,
  Typography,
} from '@mui/material';
import { useFormikContext } from 'formik';
import { useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import type { HoursPurchaseDto } from '../../../api/hoursTypes';
import { newIdempotencyKey, newUuid } from '../../../api/ids';
import { hoursService } from '../../../api/services/hoursService';
import type { CustomerDto, MachineDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikDateTimeField } from '../../../components/forms/FormikDateTimeField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog } from '../../../components/forms/StepperFormDialog';
import { AttachmentUpload } from '../../../components/meter/AttachmentUpload';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { withErrorCode } from '../shared/errorHints';
import { PAYMENT_METHOD_LABELS, PAYMENT_METHOD_OPTIONS } from '../shared/financeDisplay';
import { customerOptionLabel, machineOptionLabel } from '../shared/financeLookups';
import {
  FormikCustomerIdPicker,
  FormikMachineIdPicker,
  FormikStaffIdPicker,
} from '../shared/financePickers';
import { FormikJobSitePicker } from '../shared/lookupPickers';
import { HOURS_ERROR_HINTS } from './hoursDisplay';
import {
  CUSTOMER_FIELDS,
  emptyPurchaseValues,
  HOURS_FIELDS,
  PAYMENT_FIELDS,
  purchaseSchema,
  toPurchasePayload,
  type PurchaseValues,
} from './purchaseForm';

const METHOD_OPTIONS = [{ value: '', label: 'No payment now' }, ...PAYMENT_METHOD_OPTIONS];
const decimal = { htmlInput: { inputMode: 'decimal' as const } };

function CustomerStep({
  walkInAllowed,
  onCustomer,
}: {
  walkInAllowed: boolean;
  onCustomer: (c: CustomerDto | null) => void;
}) {
  const { values, setFieldValue } = useFormikContext<PurchaseValues>();
  return (
    <>
      {walkInAllowed && (
        <FormControl>
          <FormLabel id="customer-mode-label">Customer</FormLabel>
          <RadioGroup
            row
            aria-labelledby="customer-mode-label"
            value={values.customer_mode}
            onChange={(e) => {
              void setFieldValue('customer_mode', e.target.value);
            }}
          >
            <FormControlLabel value="EXISTING" control={<Radio />} label="Existing customer" />
            <FormControlLabel value="WALK_IN" control={<Radio />} label="New walk-in customer" />
          </RadioGroup>
        </FormControl>
      )}
      {values.customer_mode === 'EXISTING' ? (
        <FormikCustomerIdPicker
          name="customer_id"
          label="Customer"
          required
          onOptionChange={onCustomer}
        />
      ) : (
        <>
          <FormikTextField name="walk_in_name" label="Walk-in customer name" required />
          <FormikTextField name="walk_in_phone" label="Phone (optional)" />
          <Typography variant="body2" color="text.secondary">
            A walk-in gets a WALK- code; the office can register them as a full customer later.
          </Typography>
        </>
      )}
    </>
  );
}

function PaymentStep({ field, timeZone }: { field: boolean; timeZone: string }) {
  const { values, setFieldValue } = useFormikContext<PurchaseValues>();
  if (values.payment_method === '') {
    return (
      <>
        <FormikSelectField name="payment_method" label="Payment" options={METHOD_OPTIONS} />
        <Typography variant="body2" color="text.secondary">
          Hours stay awaiting payment until money is recorded and verified (or activated on credit).
        </Typography>
      </>
    );
  }
  return (
    <>
      <FormikSelectField name="payment_method" label="Payment" options={METHOD_OPTIONS} />
      <FormikTextField
        name="payment_amount"
        label="Amount received"
        helperText="Leave empty when the full purchase amount was paid."
        slotProps={decimal}
      />
      <FormikTextField name="payment_reference" label="Reference (receipt or transaction no.)" />
      <FormikDateTimeField name="received_at" label="Received at" timeZone={timeZone} required />
      {!field && (
        <FormikStaffIdPicker
          name="staff_member_id"
          label="Cash held by (empty = me)"
          helperText="The staff member who holds the money until it is handed over."
        />
      )}
      <AttachmentUpload
        label="Evidence photo (receipt or mobile-money screenshot)"
        value={values.evidence}
        onChange={(a) => {
          void setFieldValue('evidence', a);
        }}
        upload={(file) => hoursService.uploadEvidence(file, newIdempotencyKey())}
        capture="environment"
        preview
        helperText="Kept as evidence only; the payment stays claimed until someone else verifies it."
      />
    </>
  );
}

interface RecordPurchaseDialogProps {
  timeZone: string;
  /** Field work: the payment is in the recorder's own custody (no "held by" choice). */
  field?: boolean;
  walkInAllowed: boolean;
  onClose: () => void;
  onRecorded: (purchase: HoursPurchaseDto) => void;
}

/** Customer → Hours → Payment → Review. Priced by the server (rate card, approved discount). */
export function RecordPurchaseDialog({
  timeZone,
  field = false,
  walkInAllowed,
  onClose,
  onRecorded,
}: RecordPurchaseDialogProps) {
  const keyFor = useIdempotencyKey();
  const { hasPermission } = useSession();
  const [clientId] = useState(newUuid);
  const [initial] = useState(() => emptyPurchaseValues(new Date().toISOString()));
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [machine, setMachine] = useState<MachineDto | null>(null);
  return (
    <StepperFormDialog<PurchaseValues>
      open
      title={field ? 'Record customer hours' : 'New hours purchase'}
      initialValues={initial}
      validationSchema={purchaseSchema}
      submitLabel="Record purchase"
      onClose={onClose}
      steps={[
        {
          label: 'Customer',
          fields: CUSTOMER_FIELDS,
          render: () => <CustomerStep walkInAllowed={walkInAllowed} onCustomer={setCustomer} />,
        },
        {
          label: 'Hours',
          fields: HOURS_FIELDS,
          render: () => (
            <>
              <FormikMachineIdPicker
                name="machine_id"
                label="Machine"
                required
                onOptionChange={setMachine}
              />
              <FormikTextField name="hours" label="Hours bought" required slotProps={decimal} />
              {hasPermission(PERMISSIONS.tenantGeofenceRead) && (
                <FormikJobSitePicker name="job_site_id" label="Job site (optional)" />
              )}
              <FormikTextField name="note" label="Note (optional)" multiline minRows={2} />
              <Typography variant="body2" color="text.secondary">
                The price comes from your rate card and any approved discount for this customer.
              </Typography>
            </>
          ),
        },
        {
          label: 'Payment',
          fields: PAYMENT_FIELDS,
          render: () => <PaymentStep field={field} timeZone={timeZone} />,
        },
      ]}
      renderReview={(v) => (
        <>
          <KeyValueGrid
            columns={2}
            items={[
              {
                label: 'Customer',
                value:
                  v.customer_mode === 'WALK_IN'
                    ? `${v.walk_in_name.trim()} (walk-in)`
                    : customer !== null
                      ? customerOptionLabel(customer)
                      : v.customer_id,
              },
              {
                label: 'Machine',
                value: machine !== null ? machineOptionLabel(machine) : v.machine_id,
              },
              { label: 'Hours', value: `${v.hours.trim()} h` },
              {
                label: 'Payment',
                value:
                  v.payment_method === ''
                    ? 'None now'
                    : `${PAYMENT_METHOD_LABELS[v.payment_method]} ${v.payment_amount.trim() || '(full amount)'}`,
              },
              ...(v.payment_method === ''
                ? []
                : [
                    { label: 'Received at', value: formatInstantIn(v.received_at, timeZone) },
                    { label: 'Evidence', value: v.evidence === null ? 'None' : 'Photo attached' },
                  ]),
            ]}
          />
          <Alert severity="info">
            Hours activate only from verified money: someone other than you verifies the payment.
          </Alert>
        </>
      )}
      onSubmit={async (v) => {
        const body = toPurchasePayload(v, clientId, { field });
        try {
          onRecorded(await hoursService.recordPurchase(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, HOURS_ERROR_HINTS);
        }
      }}
    />
  );
}
