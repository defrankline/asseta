import { array, boolean, mixed, object, string, type ObjectSchema } from 'yup';
import type { ProductDto, ProductIn, ProductType, ProductUpdateIn } from '../../../api/types';
import type { StatusTone } from '../../../components/display/StatusChip';
import type { SelectOption } from '../../../components/forms/FormikSelectField';
import { formatMoney, SUPPORTED_CURRENCIES } from '../../../utils/money';
import { decimalField } from '../shared/validators';

export const KIND_LABELS: Readonly<Record<ProductType, string>> = {
  SUBSCRIPTION_FEE: 'Subscription fee',
  SMS_BUNDLE: 'SMS bundle',
  SERVICE: 'Service',
};

export const KIND_OPTIONS: readonly SelectOption[] = [
  { value: 'SUBSCRIPTION_FEE', label: 'Subscription fee' },
  { value: 'SMS_BUNDLE', label: 'SMS bundle' },
  { value: 'SERVICE', label: 'Service' },
];

export const KIND_TONES: Readonly<Record<string, StatusTone>> = {
  SUBSCRIPTION_FEE: 'info',
  SMS_BUNDLE: 'success',
  SERVICE: 'default',
};

/** What paying a line of each type does (ADR-006). */
export const KIND_EFFECTS: Readonly<Record<ProductType, string>> = {
  SUBSCRIPTION_FEE:
    "Priced by the tenant's negotiated rate for a billing period; when paid, the period is settled and access re-evaluated.",
  SMS_BUNDLE: "When fully paid, the bundle's SMS credits are added to the tenant SMS wallet.",
  SERVICE: 'When fully paid, the service is recorded as settled.',
};

export const CURRENCY_OPTIONS: readonly SelectOption[] = SUPPORTED_CURRENCIES.map((c) => ({
  value: c,
  label: c,
}));

export const CATALOG_ERROR_HINTS: Readonly<Record<string, string>> = {
  SMS_CREDITS_REQUIRED: 'SMS bundles need the number of SMS credits per unit.',
  SMS_CREDITS_NOT_ALLOWED: 'Only SMS bundles carry SMS credits.',
  SUBSCRIPTION_PRICE_FROM_RATE: "Subscription fees take no list price: the tenant's rate applies.",
  DUPLICATE_PRODUCT_CODE: 'Another product already uses this code.',
};

export interface PriceRow {
  currency: string;
  amount: string;
}

export interface CatalogItemValues {
  code: string;
  name: string;
  product_type: ProductType | '';
  description: string;
  taxable: boolean;
  sms_credits: string;
  prices: PriceRow[];
}

export const PRODUCT_FIELDS = ['code', 'name', 'product_type', 'description'] as const;

/** Every price row's paths, so each row's errors show before leaving the Pricing step. */
export function pricingFieldPaths(v: CatalogItemValues): string[] {
  if (v.product_type === 'SUBSCRIPTION_FEE') return [];
  return [
    'taxable',
    'sms_credits',
    ...v.prices.flatMap((_p, i) => [`prices.${String(i)}.currency`, `prices.${String(i)}.amount`]),
  ];
}

export const EMPTY_PRICE: PriceRow = { currency: 'TZS', amount: '' };

export const EMPTY_CATALOG_ITEM: CatalogItemValues = {
  code: '',
  name: '',
  product_type: '',
  description: '',
  taxable: true,
  sms_credits: '',
  prices: [EMPTY_PRICE],
};

export function valuesFromItem(i: ProductDto): CatalogItemValues {
  return {
    code: i.code,
    name: i.name,
    product_type: i.product_type,
    description: i.description ?? '',
    taxable: i.taxable,
    sms_credits: i.sms_credits === null ? '' : String(i.sms_credits),
    prices: Object.entries(i.prices).map(([currency, amount]) => ({ currency, amount })),
  };
}

const priceRow = object({
  currency: string()
    .oneOf([...SUPPORTED_CURRENCIES], 'Choose a currency')
    .required(),
  amount: decimalField('Price'),
});

export const catalogItemSchema: ObjectSchema<CatalogItemValues> = object({
  code: string()
    .trim()
    .required('Code is required')
    .max(40, 'At most 40 characters')
    .matches(/^[A-Za-z0-9_-]+$/, 'Letters, digits, - and _ only'),
  name: string().trim().required('Name is required').max(120, 'At most 120 characters'),
  product_type: mixed<ProductType | ''>()
    .oneOf(['SUBSCRIPTION_FEE', 'SMS_BUNDLE', 'SERVICE'], 'Choose a type')
    .required('Choose a type'),
  description: string().trim().max(500, 'At most 500 characters').ensure(),
  taxable: boolean().required(),
  sms_credits: string()
    .trim()
    .ensure()
    .when('product_type', {
      is: 'SMS_BUNDLE',
      then: (s) =>
        s
          .required('SMS credits are required for an SMS bundle')
          .matches(/^[1-9]\d{0,8}$/, 'A whole number of credits (at least 1)'),
    }),
  prices: array(priceRow)
    .required()
    // Subscription fees take no list price: ignore any rows left from another type.
    .when('product_type', { is: 'SUBSCRIPTION_FEE', then: (s) => s.transform(() => []) })
    .test('unique', 'One price per currency', (rows) => {
      const seen = rows.map((r) => r.currency);
      return new Set(seen).size === seen.length;
    }),
});

const orNull = (v: string): string | null => (v.trim() === '' ? null : v.trim());

/** Subscription fees carry no list price (the negotiated rate applies). */
function priceMap(v: CatalogItemValues): Record<string, string> {
  if (v.product_type === 'SUBSCRIPTION_FEE') return {};
  return Object.fromEntries(v.prices.map((p) => [p.currency, p.amount.trim()]));
}

const credits = (v: CatalogItemValues): number | null =>
  v.product_type === 'SMS_BUNDLE' ? Number.parseInt(v.sms_credits, 10) : null;

export function toCatalogCreate(v: CatalogItemValues): ProductIn {
  if (v.product_type === '') throw new Error('product_type is required');
  return {
    code: v.code.trim().toUpperCase(),
    name: v.name.trim(),
    product_type: v.product_type,
    description: orNull(v.description),
    taxable: v.taxable,
    prices: priceMap(v),
    sms_credits: credits(v),
  };
}

export function toCatalogUpdate(v: CatalogItemValues, version: number): ProductUpdateIn {
  return {
    name: v.name.trim(),
    description: orNull(v.description),
    taxable: v.taxable,
    prices: priceMap(v),
    sms_credits: credits(v),
    version,
  };
}

export const catalogItemLabel = (i: Pick<ProductDto, 'code' | 'name'>): string =>
  `${i.code} · ${i.name}`;

/** `TZS 100,000.00 · USD 40.00`, or the rate note for subscription fees. */
export function priceSummary(i: Pick<ProductDto, 'prices' | 'product_type'>): string {
  if (i.product_type === 'SUBSCRIPTION_FEE') return 'Negotiated rate';
  const entries = Object.entries(i.prices);
  return entries.length === 0
    ? 'No list price'
    : entries.map(([c, a]) => formatMoney(a, c)).join(' · ');
}
