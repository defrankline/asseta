import { object, string, type ObjectSchema } from 'yup';
import type { RateCardIn } from '../../../api/types';
import { optionalInstant, orNull, requiredDecimal } from '../shared/formRules';

export interface RateCardFormValues {
  machine_category_id: string;
  hourly_rate: string;
  minimum_hours: string;
  /** UTC ISO instant or '' for "now". */
  effective_from: string;
  reason: string;
}

export const RATE_FIELDS = ['machine_category_id', 'hourly_rate', 'minimum_hours'] as const;
export const VERSION_FIELDS = ['effective_from', 'reason'] as const;

export function emptyRateCardValues(): RateCardFormValues {
  return {
    machine_category_id: '',
    hourly_rate: '',
    minimum_hours: '0',
    effective_from: '',
    reason: '',
  };
}

export const rateCardFormSchema: ObjectSchema<RateCardFormValues> = object({
  machine_category_id: string().required('Machine category is required'),
  hourly_rate: requiredDecimal('Hourly rate'),
  minimum_hours: requiredDecimal('Minimum hours'),
  effective_from: optionalInstant(),
  reason: string()
    .trim()
    .required('Reason is required')
    .min(3, 'At least 3 characters')
    .max(500, 'At most 500 characters'),
});

/** Money and hours are sent as decimal strings. */
export function toRateCardPayload(v: RateCardFormValues): RateCardIn {
  return {
    machine_category_id: v.machine_category_id,
    hourly_rate: v.hourly_rate.trim(),
    minimum_hours: v.minimum_hours.trim(),
    effective_from: orNull(v.effective_from),
    reason: v.reason.trim(),
  };
}
