import { object, string, type ObjectSchema } from 'yup';
import type { ContractIn } from '../../../api/types';
import {
  isAfter,
  optionalInstant,
  optionalText,
  orNull,
  requiredInstant,
} from '../shared/formRules';

export interface ContractFormValues {
  contract_number: string;
  reference: string;
  job_site_id: string;
  /** UTC ISO instants ('' when empty). */
  starts_on: string;
  ends_on: string;
  notes: string;
}

export const CONTRACT_FIELDS = ['contract_number', 'reference', 'job_site_id'] as const;
export const PERIOD_FIELDS = ['starts_on', 'ends_on', 'notes'] as const;

export function emptyContractValues(now: string): ContractFormValues {
  return {
    contract_number: '',
    reference: '',
    job_site_id: '',
    starts_on: now,
    ends_on: '',
    notes: '',
  };
}

export const contractFormSchema: ObjectSchema<ContractFormValues> = object({
  contract_number: string()
    .trim()
    .required('Contract number is required')
    .max(32, 'Contract number must be at most 32 characters'),
  reference: optionalText('Reference', 200),
  job_site_id: string().ensure(),
  starts_on: requiredInstant('Start'),
  ends_on: optionalInstant().test('after-start', 'End must be after the start', function (v) {
    return isAfter((this.parent as ContractFormValues).starts_on, v);
  }),
  notes: optionalText('Notes', 2000),
});

export function toContractPayload(customerId: string, v: ContractFormValues): ContractIn {
  return {
    customer_id: customerId,
    contract_number: v.contract_number.trim(),
    reference: orNull(v.reference),
    job_site_id: orNull(v.job_site_id),
    starts_on: v.starts_on,
    ends_on: orNull(v.ends_on),
    notes: orNull(v.notes),
  };
}
