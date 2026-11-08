import { object, string, type ObjectSchema } from 'yup';
import type { CashCollectionIn, HireInvoiceDto } from '../../../api/types';
import { compareDecimal } from '../../../utils/money';
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
  /** What the money pays for: an hours purchase or an issued invoice ('' = none named yet). */
  purchase_id: string;
  invoice_id: string;
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
    purchase_id: '',
    invoice_id: '',
  };
}

const COLLECTION_LINK_MESSAGE = 'Your company policy needs the purchase or invoice this pays for';

/** `linkRequired`: CASH_CUSTODY.collection_link_required (off while the policy is unknown). */
export const fieldCollectionSchemaFor = (
  linkRequired: boolean,
): ObjectSchema<FieldCollectionValues> =>
  object({
    job_id: string().ensure(),
    customer_id: string().required('Choose the customer'),
    staff_member_id: string().ensure(),
    amount: positiveDecimalField('Amount'),
    currency: string().ensure(),
    reference: optionalText('Reference', 120),
    received_at: requiredInstant('Received at'),
    note: optionalText('Note', 1000),
    invoice_id: string().ensure(),
    purchase_id: string()
      .ensure()
      .test('link', COLLECTION_LINK_MESSAGE, function linked(v) {
        const invoice = (this.parent as { invoice_id: string }).invoice_id;
        return !linkRequired || v !== '' || invoice !== '';
      }),
  });

export const fieldCollectionSchema = fieldCollectionSchemaFor(false);

/**
 * recordCashCollection body: the caller's own custody (`staff_member_id` null) unless a custodian
 * was chosen (when the tenant lets recorders record for others); no invoice allocation (the office
 * allocates once it verifies the cash).
 */
export function toFieldCollectionPayload(
  v: FieldCollectionValues,
  clientId: string,
  invoice: Pick<HireInvoiceDto, 'id' | 'balance'> | null = null,
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
    allocations:
      invoice === null
        ? []
        : [
            {
              invoice_id: invoice.id,
              // Up to what is open; the rest stays as customer credit.
              amount:
                compareDecimal(v.amount.trim(), invoice.balance) > 0
                  ? invoice.balance
                  : v.amount.trim(),
            },
          ],
  };
}
