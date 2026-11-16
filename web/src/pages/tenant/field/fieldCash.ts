import { object, string, type ObjectSchema } from 'yup';
import type { CashCollectionIn } from '../../../api/types';
import { positiveDecimalField } from '../../platform/shared/validators';
import { optionalText, orNull, requiredInstant } from '../shared/formRules';

/** A supervisor's cash collection into their own custody (Field work). */
export interface FieldCollectionValues {
  customer_id: string;
  /** Custodian the cash is collected for ('' = the caller's own custody). */
  staff_member_id: string;
  amount: string;
  currency: string;
  reference: string;
  received_at: string;
  note: string;
  /** The hours purchase the money pays for ('' = none named yet). */
  purchase_id: string;
}

export function emptyCollectionValues(now: string): FieldCollectionValues {
  return {
    customer_id: '',
    staff_member_id: '',
    amount: '',
    currency: '',
    reference: '',
    received_at: now,
    note: '',
    purchase_id: '',
  };
}

const COLLECTION_LINK_MESSAGE = 'Your company policy needs the hours purchase this pays for';

/** `linkRequired`: CASH_CUSTODY.collection_link_required (off while the policy is unknown). */
export const fieldCollectionSchemaFor = (
  linkRequired: boolean,
): ObjectSchema<FieldCollectionValues> =>
  object({
    customer_id: string().required('Choose the customer'),
    staff_member_id: string().ensure(),
    amount: positiveDecimalField('Amount'),
    currency: string().ensure(),
    reference: optionalText('Reference', 120),
    received_at: requiredInstant('Received at'),
    note: optionalText('Note', 1000),
    purchase_id: linkRequired
      ? string().ensure().required(COLLECTION_LINK_MESSAGE)
      : string().ensure(),
  });

export const fieldCollectionSchema = fieldCollectionSchemaFor(false);

/**
 * recordCashCollection body: the caller's own custody (`staff_member_id` null) unless a custodian
 * was chosen (when the tenant lets recorders record for others).
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
    purchase_id: orNull(v.purchase_id),
  };
}
