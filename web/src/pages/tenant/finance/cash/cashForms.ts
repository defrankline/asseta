import { mixed, object, string, type ObjectSchema } from 'yup';
import type { CashFloatIn, CashHandoverIn, CustodyEntryType } from '../../../../api/types';
import { CUSTODY_ENTRY_TYPES } from '../../../../api/services/financeSchemas';
import { positiveDecimalField } from '../../../platform/shared/validators';
import { optionalText, orNull, requiredInstant } from '../../shared/formRules';

export interface FloatValues {
  staff_member_id: string;
  entry_type: CustodyEntryType;
  amount: string;
  currency: string;
  occurred_at: string;
  reference: string;
  note: string;
}

export const ENTRY_TYPE_OPTIONS: readonly { value: CustodyEntryType; label: string }[] = [
  { value: 'FLOAT_ISSUED', label: 'Float issued' },
  { value: 'OPENING_BALANCE', label: 'Opening balance' },
];

export const floatSchema: ObjectSchema<FloatValues> = object({
  staff_member_id: string().required('Choose the supervisor'),
  entry_type: mixed<CustodyEntryType>().oneOf(CUSTODY_ENTRY_TYPES).required(),
  amount: positiveDecimalField('Amount'),
  currency: string().ensure(),
  occurred_at: requiredInstant('Issued at'),
  reference: optionalText('Reference', 120),
  note: optionalText('Note', 1000),
});

export function toFloatPayload(v: FloatValues): CashFloatIn {
  return {
    staff_member_id: v.staff_member_id,
    entry_type: v.entry_type,
    amount: v.amount.trim(),
    currency: orNull(v.currency),
    occurred_at: v.occurred_at,
    reference: orNull(v.reference),
    note: orNull(v.note),
  };
}

export interface HandoverValues {
  staff_member_id: string;
  amount: string;
  currency: string;
  handed_at: string;
  reference: string;
  note: string;
}

export const handoverSchema: ObjectSchema<HandoverValues> = object({
  staff_member_id: string().ensure(),
  amount: positiveDecimalField('Amount'),
  currency: string().ensure(),
  handed_at: requiredInstant('Handed over at'),
  reference: optionalText('Reference', 120),
  note: optionalText('Note', 1000),
});

export function toHandoverPayload(v: HandoverValues, clientId: string): CashHandoverIn {
  return {
    staff_member_id: orNull(v.staff_member_id),
    amount: v.amount.trim(),
    currency: orNull(v.currency),
    handed_at: v.handed_at,
    reference: orNull(v.reference),
    note: orNull(v.note),
    client_id: clientId,
  };
}
