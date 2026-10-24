import { object, string, type ObjectSchema } from 'yup';
import type { CashCollectionIn } from '../../../api/types';
import { positiveDecimalField } from '../../platform/shared/validators';
import { optionalText, orNull, requiredInstant } from '../shared/formRules';

/** A supervisor's cash collection into their own custody (Field work). */
export interface FieldCollectionValues {
  /** Optional: picking the job fills its customer. Not sent (collections belong to customers). */
  job_id: string;
  customer_id: string;
  /** Custodian the cash is collected for ('' = the caller's own custody). */
  staff_member_id: string;
  amount: string;
  currency: string;
  reference: string;
  received_at: string;
  note: string;
}

export function emptyCollectionValues(now: string, jobId = ''): FieldCollectionValues {
  return {
    job_id: jobId,
    customer_id: '',
    staff_member_id: '',
    amount: '',
    currency: '',
    reference: '',
    received_at: now,
    note: '',
  };
}

export const fieldCollectionSchema: ObjectSchema<FieldCollectionValues> = object({
  job_id: string().ensure(),
  customer_id: string().required('Choose the customer'),
  staff_member_id: string().ensure(),
  amount: positiveDecimalField('Amount'),
  currency: string().ensure(),
  reference: optionalText('Reference', 120),
  received_at: requiredInstant('Received at'),
  note: optionalText('Note', 1000),
});

/**
 * recordCashCollection body: the caller's own custody (`staff_member_id` null) unless a custodian
 * was chosen (when the tenant lets recorders record for others); no invoice allocation (the office
 * allocates once it verifies the cash).
 */
export function toFieldCollectionPayload(
  v: FieldCollectionValues,
  clientId: string,
): CashCollectionIn {
  return {
    customer_id: v.customer_id,
    amount: v.amount.trim(),
    currency: orNull(v.currency),
    reference: orNull(v.reference),
    received_at: v.received_at,
    staff_member_id: orNull(v.staff_member_id),
    note: orNull(v.note),
    client_id: clientId,
    allocations: [],
  };
}
