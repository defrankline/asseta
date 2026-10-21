/** Runtime (Yup) response schemas for customers, contracts, rate cards, jobs and work logs. */
import { array, object, type Schema } from 'yup';
import type {
  AcknowledgementDto,
  ActivityDto,
  ActivityType,
  ContractDto,
  ContractStatus,
  CustomerDto,
  JobDto,
  JobStatus,
  JobSummaryDto,
  RateCardDto,
  StandbyTreatment,
} from '../types';
import { bool, id, int, nullableId, nullableText, oneOf, text } from './schemaKit';

export const CONTRACT_STATUSES: readonly ContractStatus[] = ['DRAFT', 'ACTIVE', 'CLOSED'];
export const JOB_STATUSES: readonly JobStatus[] = [
  'DRAFT',
  'PENDING_APPROVAL',
  'APPROVED',
  'IN_PROGRESS',
  'COMPLETED',
  'CANCELLED',
];
export const STANDBY_TREATMENTS: readonly StandbyTreatment[] = [
  'EXCLUDED',
  'INCLUDED',
  'STANDBY_RATE',
];
export const ACTIVITY_TYPES: readonly ActivityType[] = [
  'WORK',
  'STANDBY',
  'DOWNTIME',
  'MOBILIZATION',
  'NOTE',
];

export const customerSchema: Schema<CustomerDto> = object({
  id: id(),
  code: text(),
  name: text(),
  tax_id: nullableText(),
  contact_name: nullableText(),
  contact_phone: nullableText(),
  contact_email: nullableText(),
  payment_terms_days: int(),
  is_active: bool(),
});

export const contractSchema: Schema<ContractDto> = object({
  id: id(),
  customer_id: id(),
  contract_number: text(),
  job_site_id: nullableId(),
  currency: text(),
  status: oneOf(CONTRACT_STATUSES),
  starts_on: text(),
  ends_on: nullableText(),
  reference: nullableText(),
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

const jobFields = {
  id: id(),
  contract_id: id(),
  job_number: text(),
  machine_id: id(),
  job_site_id: nullableId(),
  supervisor_id: nullableId(),
  status: oneOf(JOB_STATUSES),
  planned_start: text(),
  planned_end: nullableText(),
  currency: text(),
  hourly_rate: text(),
  minimum_hours: text(),
  standby_treatment: oneOf(STANDBY_TREATMENTS),
  standby_rate: nullableText(),
  mobilization_fee: text(),
  discount_percent: text(),
  tax_rate_percent: text(),
  rate_source: text(),
  approved_at: nullableText(),
  started_at: nullableText(),
  completed_at: nullableText(),
  version: int(),
};

export const jobSchema: Schema<JobDto> = object(jobFields);

/** Priced charge lines from the server's single pricing source (absent until hours are billable). */
const chargesSchema = object({
  currency: text(),
  lines: array(
    object({
      kind: text(),
      description: text(),
      quantity: text(),
      unit_price: text(),
      amount: text(),
    }),
  ).required(),
  subtotal: text(),
  discount_total: text(),
  tax_total: text(),
  total: text(),
})
  .nullable()
  .optional()
  .default(undefined);

export const jobSummarySchema: Schema<JobSummaryDto> = object({
  job: object(jobFields).required(),
  opening_reading: nullableText(),
  closing_reading: nullableText(),
  meter_hours: nullableText(),
  nonbillable_hours: text(),
  billable_hours: nullableText(),
  standby_hours: text(),
  charges: chargesSchema,
  open_exceptions: int(),
  blocking_exceptions: int(),
  billing_ready: bool(),
  policy_version: text(),
});

export const activitySchema: Schema<ActivityDto> = object({
  id: id(),
  client_id: id(),
  activity_type: oneOf(ACTIVITY_TYPES),
  started_at: text(),
  ended_at: nullableText(),
  billable: bool(),
  note: nullableText(),
});

export const acknowledgementSchema: Schema<AcknowledgementDto> = object({
  id: id(),
  method: text(),
  signer_name: text(),
  signer_phone: nullableText(),
  signature_attachment_id: nullableId(),
  acknowledged_hours: nullableText(),
  captured_at: text(),
});
