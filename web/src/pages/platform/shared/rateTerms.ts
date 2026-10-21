import { mixed, object, string } from 'yup';
import type {
  Cadence,
  MidCycleAddPolicy,
  MidCycleRemovePolicy,
  RateTermsIn,
  RoundingMode,
} from '../../../api/types';
import { decimalField, integerField, percentField } from './validators';

/** Form values for negotiated rate terms; numerics stay strings until the payload is built. */
export interface RateTermsValues {
  currency: string;
  cadence: Cadence;
  unit_price: string;
  minimum_billable_assets: string;
  discount_percent: string;
  tax_name: string;
  tax_rate_percent: string;
  mid_cycle_add: MidCycleAddPolicy;
  mid_cycle_remove: MidCycleRemovePolicy;
  rounding_mode: RoundingMode;
}

export const RATE_TERM_DEFAULTS: RateTermsValues = {
  currency: 'TZS',
  cadence: 'MONTHLY',
  unit_price: '',
  minimum_billable_assets: '1',
  discount_percent: '0',
  tax_name: '',
  tax_rate_percent: '0',
  mid_cycle_add: 'PRORATE_DAILY',
  mid_cycle_remove: 'PRORATE_CREDIT',
  rounding_mode: 'HALF_UP',
};

/** Mirrors RateTermsIn / NewRateVersionIn constraints. */
export const rateTermsShape = {
  currency: string()
    .required('Currency is required')
    .matches(/^[A-Z]{3}$/, 'Use a 3-letter ISO currency code'),
  cadence: mixed<Cadence>().oneOf(['MONTHLY', 'YEARLY']).required('Cadence is required'),
  unit_price: decimalField('Unit price'),
  minimum_billable_assets: integerField('Minimum billable assets', 1),
  discount_percent: percentField('Discount %'),
  tax_name: string().trim().max(40, 'Tax name must be at most 40 characters').default(''),
  tax_rate_percent: percentField('Tax %'),
  mid_cycle_add: mixed<MidCycleAddPolicy>()
    .oneOf(['PRORATE_DAILY', 'FULL_PERIOD', 'NEXT_PERIOD'])
    .required(),
  mid_cycle_remove: mixed<MidCycleRemovePolicy>().oneOf(['PRORATE_CREDIT', 'NO_CREDIT']).required(),
  rounding_mode: mixed<RoundingMode>().oneOf(['HALF_UP', 'HALF_EVEN']).required(),
};
export const rateTermsSchema = object(rateTermsShape);

/** Build the API payload; money/percent values are sent as decimal strings. */
export function toRateTermsIn(v: RateTermsValues): RateTermsIn {
  const taxName = v.tax_name.trim();
  return {
    currency: v.currency,
    cadence: v.cadence,
    unit_price: v.unit_price.trim(),
    minimum_billable_assets: Number(v.minimum_billable_assets),
    discount_percent: v.discount_percent.trim(),
    tax_name: taxName === '' ? null : taxName,
    tax_rate_percent: v.tax_rate_percent.trim(),
    mid_cycle_add: v.mid_cycle_add,
    mid_cycle_remove: v.mid_cycle_remove,
    rounding_mode: v.rounding_mode,
  };
}

export const RATE_PRICE_FIELDS = [
  'currency',
  'cadence',
  'unit_price',
  'minimum_billable_assets',
] as const;
export const RATE_POLICY_FIELDS = [
  'discount_percent',
  'tax_name',
  'tax_rate_percent',
  'mid_cycle_add',
  'mid_cycle_remove',
  'rounding_mode',
] as const;

/** Prefix field names, e.g. `subscription.rate.` for the onboarding form. */
export const withPrefix = (prefix: string, fields: readonly string[]) =>
  fields.map((f) => `${prefix}${f}`);
