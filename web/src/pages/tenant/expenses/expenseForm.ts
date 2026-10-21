import { array, mixed, object, string, type ObjectSchema } from 'yup';
import type {
  AttachmentDto,
  ExpenseIn,
  ExpensePaidFrom,
  FuelEventIn,
  FuelEventType,
  GpsIn,
} from '../../../api/types';
import { FUEL_EVENT_TYPES, PAID_FROM_VALUES } from '../../../api/services/expenseSchemas';
import { positiveDecimalField } from '../../platform/shared/validators';
import { optionalDecimal, optionalText, orNull, requiredInstant } from '../shared/formRules';

export interface ExpenseFormValues {
  category_id: string;
  description: string;
  amount: string;
  currency: string;
  incurred_at: string;
  supplier: string;
  job_id: string;
  machine_id: string;
  paid_from: ExpensePaidFrom;
  custodian_staff_id: string;
  receipts: AttachmentDto[];
  gps: GpsIn | null;
}

export const EXPENSE_FIELDS = [
  'category_id',
  'description',
  'amount',
  'currency',
  'incurred_at',
  'supplier',
] as const;
export const ATTRIBUTION_FIELDS = [
  'job_id',
  'machine_id',
  'paid_from',
  'custodian_staff_id',
] as const;
export const EVIDENCE_FIELDS = ['receipts', 'gps'] as const;

export function emptyExpenseValues(now: string): ExpenseFormValues {
  return {
    category_id: '',
    description: '',
    amount: '',
    currency: '',
    incurred_at: now,
    supplier: '',
    job_id: '',
    machine_id: '',
    paid_from: 'COMPANY',
    custodian_staff_id: '',
    receipts: [],
    gps: null,
  };
}

export const expenseFormSchema: ObjectSchema<ExpenseFormValues> = object({
  category_id: string().required('Choose a category'),
  description: string()
    .trim()
    .required('Describe the expense')
    .max(2000, 'At most 2000 characters'),
  amount: positiveDecimalField('Amount'),
  currency: string().ensure(),
  incurred_at: requiredInstant('Incurred at'),
  supplier: optionalText('Supplier', 200),
  job_id: string().ensure(),
  machine_id: string().ensure(),
  paid_from: mixed<ExpensePaidFrom>().oneOf(PAID_FROM_VALUES).required(),
  custodian_staff_id: string().ensure(),
  receipts: array(mixed<AttachmentDto>().required()).required().max(10, 'At most 10 receipts'),
  gps: mixed<GpsIn>().nullable().defined(),
});

export function toExpensePayload(v: ExpenseFormValues, clientId: string): ExpenseIn {
  return {
    category_id: v.category_id,
    description: v.description.trim(),
    amount: v.amount.trim(),
    currency: orNull(v.currency),
    incurred_at: v.incurred_at,
    supplier: orNull(v.supplier),
    job_id: orNull(v.job_id),
    machine_id: orNull(v.machine_id),
    paid_from: v.paid_from,
    custodian_staff_id: v.paid_from === 'CASH_CUSTODY' ? orNull(v.custodian_staff_id) : null,
    receipt_attachment_ids: v.receipts.map((r) => r.id),
    gps: v.gps,
    client_id: clientId,
  };
}

export interface FuelFormValues {
  event_type: FuelEventType;
  litres: string;
  unit_price: string;
  currency: string;
  occurred_at: string;
  machine_id: string;
  job_id: string;
  expense_id: string;
  meter_reading: string;
  supplier: string;
  note: string;
}

export function emptyFuelValues(now: string): FuelFormValues {
  return {
    event_type: 'ISSUE',
    litres: '',
    unit_price: '',
    currency: '',
    occurred_at: now,
    machine_id: '',
    job_id: '',
    expense_id: '',
    meter_reading: '',
    supplier: '',
    note: '',
  };
}

export const fuelFormSchema: ObjectSchema<FuelFormValues> = object({
  event_type: mixed<FuelEventType>().oneOf(FUEL_EVENT_TYPES).required(),
  litres: positiveDecimalField('Litres'),
  unit_price: optionalDecimal('Unit price'),
  currency: string().ensure(),
  occurred_at: requiredInstant('Occurred at'),
  machine_id: string().ensure(),
  job_id: string().ensure(),
  expense_id: string().ensure(),
  meter_reading: optionalDecimal('Meter reading'),
  supplier: optionalText('Supplier', 200),
  note: optionalText('Note', 1000),
});

export function toFuelPayload(v: FuelFormValues, clientId: string): FuelEventIn {
  const usage = v.event_type === 'USAGE';
  return {
    event_type: v.event_type,
    litres: v.litres.trim(),
    unit_price: usage ? null : orNull(v.unit_price),
    currency: orNull(v.currency),
    occurred_at: v.occurred_at,
    machine_id: orNull(v.machine_id),
    job_id: orNull(v.job_id),
    expense_id: v.event_type === 'PURCHASE' ? orNull(v.expense_id) : null,
    meter_reading: orNull(v.meter_reading),
    supplier: orNull(v.supplier),
    note: orNull(v.note),
    client_id: clientId,
  };
}
