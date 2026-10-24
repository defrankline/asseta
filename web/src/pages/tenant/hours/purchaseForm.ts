import { mixed, object, string, type ObjectSchema } from 'yup';
import type { HoursPurchaseIn } from '../../../api/hoursTypes';
import type { AttachmentDto, HirePaymentMethod } from '../../../api/types';
import { PAYMENT_METHODS } from '../../../api/services/financeSchemas';
import { positiveDecimalField } from '../../platform/shared/validators';
import { optionalDecimal, optionalText, orNull } from '../shared/formRules';

export type CustomerMode = 'EXISTING' | 'WALK_IN';

/** Record an hours purchase: customer (or a new walk-in), machine and hours, optional payment. */
export interface PurchaseValues {
  customer_mode: CustomerMode;
  customer_id: string;
  walk_in_name: string;
  walk_in_phone: string;
  machine_id: string;
  hours: string;
  job_site_id: string;
  note: string;
  /** '' = no payment recorded with the purchase. */
  payment_method: HirePaymentMethod | '';
  /** Empty = the purchase amount. */
  payment_amount: string;
  payment_reference: string;
  received_at: string;
  /** Office only: the staff member holding the cash ('' = me). */
  staff_member_id: string;
  evidence: AttachmentDto | null;
}

export const CUSTOMER_FIELDS = [
  'customer_mode',
  'customer_id',
  'walk_in_name',
  'walk_in_phone',
] as const;
export const HOURS_FIELDS = ['machine_id', 'hours', 'job_site_id', 'note'] as const;
export const PAYMENT_FIELDS = [
  'payment_method',
  'payment_amount',
  'payment_reference',
  'received_at',
  'staff_member_id',
  'evidence',
] as const;

export function emptyPurchaseValues(now: string): PurchaseValues {
  return {
    customer_mode: 'EXISTING',
    customer_id: '',
    walk_in_name: '',
    walk_in_phone: '',
    machine_id: '',
    hours: '',
    job_site_id: '',
    note: '',
    payment_method: '',
    payment_amount: '',
    payment_reference: '',
    received_at: now,
    staff_member_id: '',
    evidence: null,
  };
}

const parent = (ctx: { parent: unknown }) => ctx.parent as PurchaseValues;

export const purchaseSchema: ObjectSchema<PurchaseValues> = object({
  customer_mode: mixed<CustomerMode>().oneOf(['EXISTING', 'WALK_IN']).required(),
  customer_id: string()
    .ensure()
    .test('customer', 'Choose the customer', function (v) {
      return parent(this).customer_mode !== 'EXISTING' || v !== '';
    }),
  walk_in_name: string()
    .trim()
    .ensure()
    .max(200, 'At most 200 characters')
    .test('name', 'Enter the walk-in customer’s name', function (v) {
      return parent(this).customer_mode !== 'WALK_IN' || v !== '';
    }),
  walk_in_phone: string()
    .trim()
    .ensure()
    .test(
      'phone',
      'Phone must be 3–40 characters',
      (v) => v === '' || (v.length >= 3 && v.length <= 40),
    ),
  machine_id: string().required('Choose the machine'),
  hours: positiveDecimalField('Hours'),
  job_site_id: string().ensure(),
  note: optionalText('Note', 1000),
  payment_method: mixed<HirePaymentMethod | ''>()
    .default('')
    .oneOf(['', ...PAYMENT_METHODS])
    .defined(),
  payment_amount: optionalDecimal('Amount'),
  payment_reference: optionalText('Reference', 120),
  received_at: string()
    .ensure()
    .test('received', 'Received at is required', function (v) {
      return parent(this).payment_method === '' || v !== '';
    })
    .test(
      'instant',
      'Enter a valid date and time',
      (v) => v === '' || !Number.isNaN(Date.parse(v)),
    ),
  staff_member_id: string().ensure(),
  evidence: mixed<AttachmentDto>().nullable().defined(),
});

/** recordHoursPurchase body. The server prices it from the rate card and approved discounts. */
export function toPurchasePayload(
  v: PurchaseValues,
  clientId: string,
  options: { field: boolean },
): HoursPurchaseIn {
  const walkIn = v.customer_mode === 'WALK_IN';
  return {
    client_id: clientId,
    customer_id: walkIn ? null : v.customer_id,
    walk_in: walkIn
      ? { name: v.walk_in_name.trim(), phone: orNull(v.walk_in_phone), client_id: clientId }
      : null,
    machine_id: v.machine_id,
    hours: v.hours.trim(),
    job_site_id: orNull(v.job_site_id),
    note: orNull(v.note),
    payment:
      v.payment_method === ''
        ? null
        : {
            method: v.payment_method,
            amount: orNull(v.payment_amount),
            reference: orNull(v.payment_reference),
            received_at: v.received_at,
            staff_member_id: options.field ? null : orNull(v.staff_member_id),
            evidence_attachment_ids: v.evidence === null ? [] : [v.evidence.id],
          },
  };
}
