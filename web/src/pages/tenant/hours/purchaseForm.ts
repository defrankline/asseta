import { array, boolean, mixed, object, string, type ObjectSchema } from 'yup';
import type { HoursPurchaseIn } from '../../../api/hoursTypes';
import type { AttachmentDto, HirePaymentMethod } from '../../../api/types';
import { PAYMENT_METHODS } from '../../../api/services/financeSchemas';
import { positiveDecimalField } from '../../platform/shared/validators';
import { compareDecimal, isDecimalString, sumDecimals } from '../../../utils/money';
import { optionalText, orNull } from '../shared/formRules';
import { remainingBalance } from './hoursQuote';

export type CustomerMode = 'EXISTING' | 'WALK_IN';

/** One part of the bill (cash, bank or mobile money). */
export interface PaymentLine {
  /** Stable React key only; never sent. */
  key: string;
  method: HirePaymentMethod;
  amount: string;
  reference: string;
  received_at: string;
  /** Office only: the staff member holding the cash ('' = me). */
  staff_member_id: string;
  evidence: AttachmentDto | null;
  /** The opening Cash line: its amount follows the quote total until the user types into it. Never sent. */
  follows_total: boolean;
}

export const NEEDS_REFERENCE: ReadonlySet<HirePaymentMethod> = new Set(['BANK', 'MOBILE_MONEY']);
export const MAX_PAYMENT_LINES = 10;

/** Record an hours purchase: customer (or a new walk-in), machine and hours, optional payment. */
export interface PurchaseValues {
  customer_mode: CustomerMode;
  customer_id: string;
  walk_in_name: string;
  walk_in_phone: string;
  machine_id: string;
  hours: string;
  job_site_id: string;
  note: string;
  /** Opens with one Cash line that follows the total; empty = not paid yet. */
  payments: PaymentLine[];
  /** The live quote total ('' while unknown); only used to stop over-payment. Never sent. */
  quote_amount: string;
  quote_currency: string;
}

export const CUSTOMER_FIELDS = [
  'customer_mode',
  'customer_id',
  'walk_in_name',
  'walk_in_phone',
] as const;
export const HOURS_FIELDS = ['machine_id', 'hours', 'job_site_id', 'note'] as const;
export const PAYMENT_FIELDS = ['payments'] as const;

/** Every line's fields, so each row shows its errors before leaving the step. */
export function paymentFieldsFor(v: PurchaseValues): string[] {
  return [
    'payments',
    ...v.payments.flatMap((_, i) => [
      `payments[${i}].method`,
      `payments[${i}].amount`,
      `payments[${i}].reference`,
      `payments[${i}].received_at`,
    ]),
  ];
}

/** Sum of the lines with a valid amount. */
export function paidSoFar(lines: readonly PaymentLine[]): string {
  return sumDecimals([
    '0',
    ...lines
      .map((l) => (l as Partial<PaymentLine> | undefined)?.amount?.trim() ?? '')
      .filter(isDecimalString),
  ]);
}

/** True when the lines add up to more than the known total. */
export function paymentsExceedTotal(v: Pick<PurchaseValues, 'payments' | 'quote_amount'>): boolean {
  return (
    v.quote_amount !== '' &&
    v.payments.length > 0 &&
    compareDecimal(paidSoFar(v.payments), v.quote_amount) > 0
  );
}

export const OVER_TOTAL_TEXT = 'The payments add up to more than the total. Lower an amount.';

export function emptyPaymentLine(
  method: HirePaymentMethod,
  amount: string,
  now: string,
  followsTotal = false,
): PaymentLine {
  return {
    key: Math.random().toString(36).slice(2),
    method,
    amount,
    reference: '',
    received_at: now,
    staff_member_id: '',
    evidence: null,
    follows_total: followsTotal,
  };
}

/**
 * Lines still following the total take the quote total ('' while unknown); typed lines are left alone.
 * Null when nothing changes.
 */
export function followTotal(lines: readonly PaymentLine[], total: string): PaymentLine[] | null {
  const amount = remainingBalance('0', total);
  if (!lines.some((l) => l.follows_total && l.amount !== amount)) return null;
  return lines.map((l) => (l.follows_total && l.amount !== amount ? { ...l, amount } : l));
}

export function emptyPurchaseValues(): PurchaseValues {
  return {
    customer_mode: 'EXISTING',
    customer_id: '',
    walk_in_name: '',
    walk_in_phone: '',
    machine_id: '',
    hours: '',
    job_site_id: '',
    note: '',
    payments: [emptyPaymentLine('CASH', '', new Date().toISOString(), true)],
    quote_amount: '',
    quote_currency: '',
  };
}

const parent = (ctx: { parent: unknown }) => ctx.parent as PurchaseValues;

export const purchaseSchema: ObjectSchema<PurchaseValues> = object({
  customer_mode: mixed<CustomerMode>().oneOf(['EXISTING', 'WALK_IN']).required(),
  customer_id: string()
    .ensure()
    .test('customer', 'Choose the customer', function (v) {
      return parent(this).customer_mode !== 'EXISTING' || v !== '';
    }),
  walk_in_name: string()
    .trim()
    .ensure()
    .max(200, 'At most 200 characters')
    .test('name', 'Enter the walk-in customer’s name', function (v) {
      return parent(this).customer_mode !== 'WALK_IN' || v !== '';
    }),
  walk_in_phone: string()
    .trim()
    .ensure()
    .test(
      'phone',
      'Phone must be 3–40 characters',
      (v) => v === '' || (v.length >= 3 && v.length <= 40),
    ),
  machine_id: string().required('Choose the machine'),
  hours: positiveDecimalField('Hours'),
  job_site_id: string().ensure(),
  note: optionalText('Note', 1000),
  payments: array(
    object({
      key: string().required(),
      method: mixed<HirePaymentMethod>()
        .oneOf([...PAYMENT_METHODS])
        .required('Choose the method'),
      amount: positiveDecimalField('Amount'),
      reference: optionalText('Reference', 120).test(
        'reference',
        'Reference is required for bank and mobile money',
        function (v) {
          const line = this.parent as PaymentLine;
          return !NEEDS_REFERENCE.has(line.method) || v.trim() !== '';
        },
      ),
      received_at: string()
        .required('Received at is required')
        .test('instant', 'Enter a valid date and time', (v) => !Number.isNaN(Date.parse(v))),
      staff_member_id: string().ensure(),
      evidence: mixed<AttachmentDto>().nullable().defined(),
      follows_total: boolean().defined(),
    }),
  )
    .max(MAX_PAYMENT_LINES, `At most ${MAX_PAYMENT_LINES} payments`)
    .required()
    .test('total', OVER_TOTAL_TEXT, function (v) {
      return !paymentsExceedTotal({
        payments: v,
        quote_amount: parent(this).quote_amount,
      });
    }),
  quote_amount: string().ensure(),
  quote_currency: string().ensure(),
});

/** recordHoursPurchase body. The server prices it from the rate card and approved discounts. */
export function toPurchasePayload(
  v: PurchaseValues,
  clientId: string,
  options: { field: boolean },
): HoursPurchaseIn {
  const walkIn = v.customer_mode === 'WALK_IN';
  return {
    client_id: clientId,
    customer_id: walkIn ? null : v.customer_id,
    walk_in: walkIn
      ? { name: v.walk_in_name.trim(), phone: orNull(v.walk_in_phone), client_id: clientId }
      : null,
    machine_id: v.machine_id,
    hours: v.hours.trim(),
    job_site_id: orNull(v.job_site_id),
    note: orNull(v.note),
    payments: v.payments.map((l) => ({
      method: l.method,
      amount: l.amount.trim(),
      reference: orNull(l.reference),
      received_at: l.received_at,
      staff_member_id: options.field ? null : orNull(l.staff_member_id),
      evidence_attachment_ids: l.evidence === null ? [] : [l.evidence.id],
    })),
  };
}
