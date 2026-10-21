import { array, object, string, type ObjectSchema } from 'yup';
import { customerPaymentService } from '../../../../api/services/financeService';
import type { CustomerPaymentDto, HireAllocateIn } from '../../../../api/types';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { FormDialog } from '../../../../components/forms/FormDialog';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { compareDecimal, isDecimalString, sumDecimals } from '../../../../utils/money';
import { withErrorCode } from '../../shared/errorHints';
import { FINANCE_ERROR_HINTS } from '../../shared/financeDisplay';
import { AllocationFields } from './AllocationFields';
import {
  allocationRow,
  formText,
  toAllocations,
  unallocatedOf,
  type AllocationRow,
} from './paymentForm';

interface AllocateValues {
  customer_id: string;
  currency: string;
  allocations: AllocationRow[];
}

function schemaFor(available: string): ObjectSchema<AllocateValues> {
  return object({
    customer_id: string().required(),
    currency: string().required(),
    allocations: array(allocationRow)
      .required()
      .min(1, 'Add at least one invoice')
      .max(50, 'At most 50 allocations')
      .test('total', 'Allocations exceed the unallocated amount', (rows) => {
        const amounts = rows.map((r) => formText(r.amount));
        if (!amounts.every(isDecimalString)) return true;
        return compareDecimal(sumDecimals(amounts), available) <= 0;
      })
      .test('currency', 'Every invoice must be in the payment currency', function check(rows) {
        const cur = (this.parent as AllocateValues).currency;
        return rows.every((r) => r.invoice === null || r.invoice.currency === cur);
      }),
  });
}

interface AllocatePaymentDialogProps {
  payment: CustomerPaymentDto;
  onClose: () => void;
  onAllocated: (payment: CustomerPaymentDto) => void;
}

/** Apply (part of) a payment to the customer's issued invoices. Mount only while open. */
export function AllocatePaymentDialog({
  payment,
  onClose,
  onAllocated,
}: AllocatePaymentDialogProps) {
  const keyFor = useIdempotencyKey();
  const available = unallocatedOf(payment);
  return (
    <FormDialog<AllocateValues>
      open
      title="Allocate payment to invoices"
      maxWidth="md"
      initialValues={{
        customer_id: payment.customer_id,
        currency: payment.currency,
        allocations: [{ invoice: null, amount: '' }],
      }}
      validationSchema={schemaFor(available)}
      submitLabel="Allocate"
      onClose={onClose}
      onSubmit={async (v) => {
        const body: HireAllocateIn = { allocations: toAllocations(v.allocations) };
        try {
          onAllocated(await customerPaymentService.allocate(payment.id, body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, FINANCE_ERROR_HINTS);
        }
      }}
    >
      <KeyValueGrid
        columns={2}
        items={[
          {
            label: 'Payment',
            value: <MoneyText amount={payment.amount} currency={payment.currency} />,
          },
          {
            label: 'Unallocated',
            value: <MoneyText amount={available} currency={payment.currency} strong />,
          },
        ]}
      />
      <AllocationFields intro="Partial amounts are allowed. Allocations of a CLAIMED payment reserve the invoice amount; they count as paid once the payment is verified." />
    </FormDialog>
  );
}
