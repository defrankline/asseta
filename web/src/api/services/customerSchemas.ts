/** Runtime (Yup) response schemas for customers and rate cards. */
import { object, type Schema } from 'yup';
import type { CustomerDto, RateCardDto } from '../types';
import { bool, id, int, nullableText, oneOf, text, lifecycleFields } from './schemaKit';

export const CUSTOMER_KINDS: readonly CustomerDto['kind'][] = ['REGISTERED', 'WALK_IN'];

export const customerSchema: Schema<CustomerDto> = object({
  id: id(),
  code: text(),
  name: text(),
  tax_id: nullableText(),
  contact_name: nullableText(),
  contact_phone: nullableText(),
  contact_email: nullableText(),
  payment_terms_days: int(),
  kind: oneOf(CUSTOMER_KINDS),
  is_active: bool(),
  ...lifecycleFields(),
});

export const rateCardSchema: Schema<RateCardDto> = object({
  id: id(),
  machine_category_id: id(),
  effective_from: text(),
  hourly_rate: text(),
  minimum_hours: text(),
  currency: text(),
  reason: text(),
});
