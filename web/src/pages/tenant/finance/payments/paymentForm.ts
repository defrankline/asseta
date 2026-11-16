import { mixed, object, string, type ObjectSchema } from 'yup';
import type { CashCollectionIn, CustomerPaymentIn, HirePaymentMethod } from '../../../../api/types';
import { PAYMENT_METHODS } from '../../../../api/services/financeSchemas';
import { optionalText, orNull, requiredInstant } from '../../shared/formRules';
import { positiveDecimalField } from '../../../platform/shared/validators';

/** Formik passes '' to Yup as undefined; read untyped form strings defensively in tests. */
export const formText = (v: unknown): string => (typeof v === 'string' ? v.trim() : '');

export interface PaymentFormValues {
  customer_id: string;
  method: HirePaymentMethod;
  amount: string;
  currency: string;
  reference: string;
  received_at: string;
  received_by_staff_id: string;
  note: string;
  /** Collections only: the hours purchase this cash pays for ('' = none). */
  purchase_id: string;
}

export const PAYMENT_FIELDS = ['customer_id', 'method', 'amount', 'currency', 'reference'] as const;
export const RECEIPT_FIELDS = ['received_at', 'received_by_staff_id', 'note'] as const;
export const PURCHASE_FIELDS = ['purchase_id'] as const;

/** Methods whose reference (bank / mobile money transaction id) is mandatory. */
export const REFERENCE_REQUIRED: ReadonlySet<HirePaymentMethod> = new Set(['BANK', 'MOBILE_MONEY']);

export function emptyPaymentValues(
  now: string,
  init: { customerId?: string; method?: HirePaymentMethod } = {},
): PaymentFormValues {
  return {
    customer_id: init.customerId ?? '',
    method: init.method ?? 'BANK',
    amount: '',
    currency: '',
    reference: '',
    received_at: now,
    received_by_staff_id: '',
    note: '',
    purchase_id: '',
  };
}

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
  purchase_id: string().ensure(),
});

/** `linkRequired`: a cash collection must name the hours purchase it pays for (CASH_CUSTODY policy). */
export const paymentFormSchemaFor = (linkRequired: boolean): ObjectSchema<PaymentFormValues> =>
  linkRequired
    ? paymentFormSchema.shape({
        purchase_id: string()
          .ensure()
          .required('Your company policy needs the hours purchase this pays for'),
      })
    : paymentFormSchema;

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
    purchase_id: orNull(v.purchase_id),
  };
}
