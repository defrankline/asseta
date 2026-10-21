import { array, mixed, object, string, type ObjectSchema } from 'yup';
import type {
  CashCollectionIn,
  CustomerPaymentDto,
  CustomerPaymentIn,
  HireAllocationIn,
  HireInvoiceDto,
  HirePaymentMethod,
} from '../../../../api/types';
import { compareDecimal, isDecimalString, sumDecimals } from '../../../../utils/money';
import { PAYMENT_METHODS } from '../../../../api/services/financeSchemas';
import { optionalText, orNull, requiredInstant } from '../../shared/formRules';
import { positiveDecimalField } from '../../../platform/shared/validators';

/** Formik passes '' to Yup as undefined; read untyped form strings defensively in tests. */
export const formText = (v: unknown): string => (typeof v === 'string' ? v.trim() : '');

export interface AllocationRow {
  /** The issued invoice picked from the server search (kept for labels and checks). */
  invoice: HireInvoiceDto | null;
  amount: string;
}

export interface PaymentFormValues {
  customer_id: string;
  method: HirePaymentMethod;
  amount: string;
  currency: string;
  reference: string;
  received_at: string;
  received_by_staff_id: string;
  note: string;
  allocations: AllocationRow[];
}

export const PAYMENT_FIELDS = ['customer_id', 'method', 'amount', 'currency', 'reference'] as const;
export const RECEIPT_FIELDS = ['received_at', 'received_by_staff_id', 'note'] as const;
export const ALLOCATION_FIELDS = ['allocations'] as const;

/** Methods whose reference (bank / mobile money transaction id) is mandatory. */
export const REFERENCE_REQUIRED: ReadonlySet<HirePaymentMethod> = new Set(['BANK', 'MOBILE_MONEY']);

export function emptyPaymentValues(
  now: string,
  init: { customerId?: string; invoice?: HireInvoiceDto; method?: HirePaymentMethod } = {},
): PaymentFormValues {
  return {
    customer_id: init.customerId ?? init.invoice?.customer_id ?? '',
    method: init.method ?? 'BANK',
    amount: '',
    currency: init.invoice?.currency ?? '',
    reference: '',
    received_at: now,
    received_by_staff_id: '',
    note: '',
    allocations: init.invoice === undefined ? [] : [{ invoice: init.invoice, amount: '' }],
  };
}

export const allocationRow: ObjectSchema<AllocationRow> = object({
  invoice: mixed<HireInvoiceDto>()
    .nullable()
    .defined()
    .test('picked', 'Choose an issued invoice', (v) => v !== null),
  amount: positiveDecimalField('Allocated amount').test(
    'open',
    'More than the invoice’s open balance',
    function check(v) {
      const inv = (this.parent as AllocationRow).invoice;
      return inv === null || !isDecimalString(v) || compareDecimal(v, inv.balance) <= 0;
    },
  ),
});

export const paymentFormSchema: ObjectSchema<PaymentFormValues> = object({
  customer_id: string().required('Choose the customer'),
  method: mixed<HirePaymentMethod>().oneOf(PAYMENT_METHODS).required(),
  amount: positiveDecimalField('Amount'),
  currency: string().ensure(),
  reference: optionalText('Reference', 120).when('method', {
    is: (m: HirePaymentMethod) => REFERENCE_REQUIRED.has(m),
    then: (s) => s.required('A reference is required for bank and mobile money payments'),
  }),
  received_at: requiredInstant('Received at'),
  received_by_staff_id: string().ensure(),
  note: optionalText('Note', 1000),
  allocations: array(allocationRow)
    .required()
    .max(50, 'At most 50 allocations')
    .test('total', 'Allocations exceed the payment amount', function check(rows) {
      const amount = formText((this.parent as Record<string, unknown>).amount);
      const amounts = rows.map((r) => formText(r.amount));
      if (!isDecimalString(amount) || !amounts.every(isDecimalString)) return true;
      return compareDecimal(sumDecimals(amounts), amount) <= 0;
    })
    .test('currency', 'Every invoice must be in the payment currency', function check(rows) {
      const cur = formText((this.parent as Record<string, unknown>).currency);
      return cur === '' || rows.every((r) => r.invoice === null || r.invoice.currency === cur);
    })
    .test('unique', 'An invoice is listed twice', (rows) => {
      const ids = rows.flatMap((r) => (r.invoice === null ? [] : [r.invoice.id]));
      return new Set(ids).size === ids.length;
    }),
});

export function toAllocations(rows: readonly AllocationRow[]): HireAllocationIn[] {
  return rows.flatMap((r) =>
    r.invoice === null ? [] : [{ invoice_id: r.invoice.id, amount: r.amount.trim() }],
  );
}

export function toPaymentPayload(v: PaymentFormValues, clientId: string): CustomerPaymentIn {
  return {
    customer_id: v.customer_id,
    method: v.method,
    amount: v.amount.trim(),
    currency: orNull(v.currency),
    reference: orNull(v.reference),
    received_at: v.received_at,
    received_by_staff_id: orNull(v.received_by_staff_id),
    note: orNull(v.note),
    client_id: clientId,
    allocations: toAllocations(v.allocations),
  };
}

/** Cash collection: always CASH, into the custodian's custody (defaults to the caller's own). */
export function toCollectionPayload(v: PaymentFormValues, clientId: string): CashCollectionIn {
  return {
    customer_id: v.customer_id,
    amount: v.amount.trim(),
    currency: orNull(v.currency),
    reference: orNull(v.reference),
    received_at: v.received_at,
    staff_member_id: orNull(v.received_by_staff_id),
    note: orNull(v.note),
    client_id: clientId,
    allocations: toAllocations(v.allocations),
  };
}

/** Payment amount minus its active (unreleased) allocations — exact BigInt arithmetic. */
export function unallocatedOf(p: CustomerPaymentDto): string {
  const active = p.allocations.filter((a) => a.released_at === null);
  return sumDecimals([p.amount, ...active.map((a) => `-${a.amount}`)]);
}
