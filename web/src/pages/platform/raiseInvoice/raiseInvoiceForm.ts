import { array, mixed, object, string, type ObjectSchema } from 'yup';
import type { AdHocInvoiceIn, AdHocLineIn, ProductType } from '../../../api/types';
import { todayIsoDate } from '../../../utils/dates';
import { SUPPORTED_CURRENCIES } from '../../../utils/money';
import { percentField, positiveDecimalField } from '../shared/validators';

/**
 * One invoice line; `product_type` / `priced_in` mirror the picked product (not submitted).
 * Subscription-fee lines only take a period start (priced by the tenant's negotiated rate).
 */
export interface RaiseLineValues {
  product_id: string;
  product_type: ProductType | '';
  /** Currencies the product has a list price in. */
  priced_in: string[];
  description: string;
  quantity: string;
  /** Negotiated unit price; empty = the catalog price in the invoice currency. */
  unit_price: string;
  discount_percent: string;
  period_start: string;
}

export interface RaiseInvoiceValues {
  tenant_id: string;
  /** Empty = the tenant's subscription currency. */
  currency: string;
  /** Empty = today + the agreement's payment terms. */
  due_date: string;
  notes: string;
  lines: RaiseLineValues[];
}

export const MAX_LINES = 50;
export const TERMS_FIELDS = ['tenant_id', 'currency', 'due_date', 'notes'] as const;
const LINE_FIELDS = [
  'product_id',
  'quantity',
  'unit_price',
  'discount_percent',
  'period_start',
  'description',
] as const;

/** Every row's field paths, so each row's errors show before leaving the Lines step. */
export function lineFieldPaths(values: RaiseInvoiceValues): string[] {
  return values.lines.flatMap((_l, i) => LINE_FIELDS.map((f) => `lines.${String(i)}.${f}`));
}

export const EMPTY_LINE: RaiseLineValues = {
  product_id: '',
  product_type: '',
  priced_in: [],
  description: '',
  quantity: '1',
  unit_price: '',
  discount_percent: '0',
  period_start: '',
};

export function emptyRaiseInvoice(tenantId = ''): RaiseInvoiceValues {
  return { tenant_id: tenantId, currency: '', due_date: '', notes: '', lines: [EMPTY_LINE] };
}

const DECIMAL = /^\d+(\.\d{1,4})?$/;
const isSubscription = (t: unknown) => t === 'SUBSCRIPTION_FEE';

const lineSchema: ObjectSchema<RaiseLineValues> = object({
  product_id: string().required('Choose a catalog item'),
  product_type: mixed<ProductType | ''>()
    .oneOf(['', 'SUBSCRIPTION_FEE', 'SMS_BUNDLE', 'SERVICE'])
    .defined(),
  priced_in: array(string().required()).required(),
  description: string().trim().max(300, 'At most 300 characters').ensure(),
  quantity: positiveDecimalField('Quantity').when('product_type', {
    is: 'SMS_BUNDLE',
    then: (s) => s.matches(/^\d+$/, 'SMS bundles are sold in whole units'),
  }),
  unit_price: string()
    .trim()
    .ensure()
    .test('decimal', 'Unit price must be a number with at most 4 decimal places', (v) =>
      v === '' ? true : DECIMAL.test(v),
    ),
  discount_percent: percentField('Discount %'),
  period_start: string()
    .ensure()
    .when('product_type', {
      is: isSubscription,
      then: (s) => s.required('Period start is required for a subscription fee'),
    }),
});

export const raiseInvoiceSchema: ObjectSchema<RaiseInvoiceValues> = object({
  tenant_id: string().required('Choose a tenant'),
  currency: string()
    .ensure()
    .test('currency', 'Choose a currency', (v) =>
      v === '' ? true : (SUPPORTED_CURRENCIES as readonly string[]).includes(v),
    ),
  due_date: string()
    .ensure()
    .test('not-past', 'Due date cannot be in the past', (v) => v === '' || v >= todayIsoDate()),
  notes: string().trim().max(2000, 'At most 2000 characters').ensure(),
  lines: array(lineSchema)
    .required()
    .min(1, 'Add at least one line')
    .max(MAX_LINES, `At most ${String(MAX_LINES)} lines`),
})
  .test('one-period', 'One subscription period per invoice', function check(v) {
    const subs = v.lines.flatMap((l, i) => (isSubscription(l.product_type) ? [i] : []));
    const second = subs[1];
    if (second === undefined) return true;
    return this.createError({
      path: `lines.${String(second)}.product_id`,
      message: 'One subscription period per invoice (DUPLICATE_PERIOD_LINE).',
    });
  })
  .test('price-in-currency', 'No list price', function check(v) {
    // Without a negotiated unit price the catalog price in the invoice currency is used.
    if (v.currency === '') return true;
    const index = v.lines.findIndex(
      (l) =>
        l.product_id !== '' &&
        !isSubscription(l.product_type) &&
        l.unit_price.trim() === '' &&
        !l.priced_in.includes(v.currency),
    );
    if (index < 0) return true;
    return this.createError({
      path: `lines.${String(index)}.unit_price`,
      message: `This item has no ${v.currency} list price: enter a negotiated unit price.`,
    });
  });

const orNull = (v: string): string | null => (v.trim() === '' ? null : v.trim());

function toLine(l: RaiseLineValues): AdHocLineIn {
  if (isSubscription(l.product_type)) {
    return {
      product_id: l.product_id,
      quantity: '1',
      discount_percent: '0',
      unit_price: null,
      period_start: l.period_start,
      description: orNull(l.description),
    };
  }
  return {
    product_id: l.product_id,
    quantity: l.quantity.trim(),
    unit_price: orNull(l.unit_price),
    discount_percent: l.discount_percent.trim() === '' ? '0' : l.discount_percent.trim(),
    period_start: null,
    description: orNull(l.description),
  };
}

/** Request body (decimal strings as typed; the server computes every amount and total). */
export function toRaiseBody(v: RaiseInvoiceValues): AdHocInvoiceIn {
  return {
    tenant_id: v.tenant_id,
    currency: orNull(v.currency),
    due_date: orNull(v.due_date),
    notes: orNull(v.notes),
    lines: v.lines.map(toLine),
  };
}

export const RAISE_ERROR_HINTS: Readonly<Record<string, string>> = {
  PERIOD_ALREADY_BILLED:
    'That subscription period is already invoiced; void that invoice first or pick another period.',
  INVALID_PERIOD: 'Use a period start that matches the billing cycle (see the message).',
  PERIOD_REQUIRED: 'Subscription lines need a period start.',
  NO_SUBSCRIPTION: 'This tenant has no subscription; remove the subscription line.',
  NOT_BILLABLE: 'The subscription is not in a billable state.',
  DUPLICATE_PERIOD_LINE: 'Only one subscription period per invoice.',
  PRODUCT_INACTIVE: 'A catalog item was deactivated; pick another item.',
  NO_PRICE: 'Enter a negotiated unit price for the item without a list price.',
  CURRENCY_MISMATCH: "The subscription rate is in another currency than the invoice's.",
  WHOLE_UNITS_REQUIRED: 'SMS bundles are sold in whole units.',
  DUE_DATE_PAST: 'The due date cannot be in the past.',
};
