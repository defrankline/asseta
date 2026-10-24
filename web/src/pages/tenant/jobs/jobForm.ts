import { mixed, object, string, type ObjectSchema } from 'yup';
import type { BillingMode } from '../../../api/hoursTypes';
import type {
  ContractDto,
  JobDto,
  JobIn,
  JobStatus,
  JobUpdateIn,
  MachineDto,
  StaffDto,
  StandbyTreatment,
} from '../../../api/types';
import { BILLING_MODES, STANDBY_TREATMENTS } from '../../../api/services/jobSchemas';
import {
  isAfter,
  optionalDecimal,
  optionalInstant,
  orNull,
  percentDecimal,
  requiredDecimal,
  requiredInstant,
} from '../shared/formRules';
import { JOB_ERROR_HINTS, PENDING_PRICE } from '../shared/jobDisplay';

/** Where the hourly price comes from: the tenant rate card (server-resolved) or a negotiated rate. */
export type RateMode = 'RATE_CARD' | 'NEGOTIATED';

export interface JobFormValues {
  contract: ContractDto | null;
  job_number: string;
  machine: MachineDto | null;
  job_site_id: string;
  supervisor: StaffDto | null;
  planned_start: string;
  planned_end: string;
  rate_mode: RateMode;
  hourly_rate: string;
  minimum_hours: string;
  standby_treatment: StandbyTreatment;
  standby_rate: string;
  mobilization_fee: string;
  discount_percent: string;
  tax_rate_percent: string;
  /** '' = the company default (CUSTOMER_HOURS policy); shown only when customer hours are on. */
  billing_mode: BillingMode | '';
}

export const ASSIGNMENT_FIELDS = [
  'contract',
  'job_number',
  'machine',
  'job_site_id',
  'supervisor',
] as const;
export const SCHEDULE_FIELDS = ['planned_start', 'planned_end'] as const;
export const PRICING_FIELDS = [
  'rate_mode',
  'hourly_rate',
  'minimum_hours',
  'standby_treatment',
  'standby_rate',
  'mobilization_fee',
  'discount_percent',
  'tax_rate_percent',
  'billing_mode',
] as const;

export function emptyJobValues(now: string): JobFormValues {
  return {
    contract: null,
    job_number: '',
    machine: null,
    job_site_id: '',
    supervisor: null,
    planned_start: now,
    planned_end: '',
    rate_mode: 'RATE_CARD',
    hourly_rate: '',
    minimum_hours: '',
    standby_treatment: 'EXCLUDED',
    standby_rate: '',
    mobilization_fee: '0',
    discount_percent: '0',
    tax_rate_percent: '0',
    billing_mode: '',
  };
}

const parentOf = (ctx: { parent: unknown }) => ctx.parent as JobFormValues;

export const jobFormSchema: ObjectSchema<JobFormValues> = object({
  contract: mixed<ContractDto>()
    .nullable()
    .defined()
    .test('contract', 'Choose a contract', (v) => v !== null),
  job_number: string()
    .trim()
    .required('Job number is required')
    .max(32, 'Job number must be at most 32 characters'),
  machine: mixed<MachineDto>()
    .nullable()
    .defined()
    .test('machine', 'Choose a machine', (v) => v !== null),
  job_site_id: string().ensure(),
  supervisor: mixed<StaffDto>().nullable().defined(),
  planned_start: requiredInstant('Planned start'),
  planned_end: optionalInstant().test('after', 'Planned end must be after the start', function (v) {
    return isAfter(parentOf(this).planned_start, v);
  }),
  rate_mode: mixed<RateMode>().oneOf(['RATE_CARD', 'NEGOTIATED']).required(),
  hourly_rate: optionalDecimal('Hourly rate').test(
    'negotiated',
    'Enter the negotiated hourly rate',
    function (v) {
      return parentOf(this).rate_mode !== 'NEGOTIATED' || v !== '';
    },
  ),
  minimum_hours: optionalDecimal('Minimum hours'),
  standby_treatment: mixed<StandbyTreatment>().oneOf(STANDBY_TREATMENTS).required(),
  standby_rate: optionalDecimal('Standby rate').test(
    'standby',
    'Enter the standby rate',
    function (v) {
      return parentOf(this).standby_treatment !== 'STANDBY_RATE' || v !== '';
    },
  ),
  mobilization_fee: requiredDecimal('Mobilization fee'),
  discount_percent: percentDecimal('Discount'),
  tax_rate_percent: percentDecimal('Tax rate'),
  billing_mode: mixed<BillingMode | ''>()
    .default('')
    .oneOf(['', ...BILLING_MODES])
    .defined(),
});

/**
 * Money, hours and percentages are sent as decimal strings. `hourly_rate` is null for the rate card
 * (the server resolves the card in force at the planned start); `standby_rate` only with STANDBY_RATE.
 */
export function toJobPayload(v: JobFormValues): JobIn {
  return {
    contract_id: v.contract?.id ?? '',
    job_number: v.job_number.trim(),
    machine_id: v.machine?.id ?? '',
    job_site_id: orNull(v.job_site_id),
    supervisor_id: v.supervisor?.id ?? null,
    planned_start: v.planned_start,
    planned_end: orNull(v.planned_end),
    hourly_rate: v.rate_mode === 'NEGOTIATED' ? v.hourly_rate.trim() : null,
    minimum_hours: orNull(v.minimum_hours),
    standby_treatment: v.standby_treatment,
    standby_rate: v.standby_treatment === 'STANDBY_RATE' ? v.standby_rate.trim() : null,
    mobilization_fee: v.mobilization_fee.trim(),
    discount_percent: v.discount_percent.trim(),
    tax_rate_percent: v.tax_rate_percent.trim(),
    billing_mode: v.billing_mode === '' ? null : v.billing_mode,
  };
}

/** A job's terms can be edited until it is approved (the API answers JOB_LOCKED afterwards). */
export const EDITABLE_JOB_STATUSES: readonly JobStatus[] = ['DRAFT', 'PENDING_APPROVAL'];

export const JOB_EDIT_ERROR_HINTS: Readonly<Record<string, string>> = {
  ...JOB_ERROR_HINTS,
  JOB_LOCKED: 'Approved, running and finished jobs can no longer be edited.',
  MACHINE_INACTIVE: 'The chosen machine is retired; choose an active machine.',
  SITE_INACTIVE: 'The chosen job site is inactive; choose an active site.',
  STAFF_INACTIVE: 'The chosen supervisor is inactive; choose an active staff member.',
};

/**
 * Edit-form values from a job. A negotiated job keeps its rate and minimum; a rate-card job
 * re-derives both from the rate card (empty fields) when saved.
 */
export function jobToValues(
  job: JobDto,
  contract: ContractDto,
  machine: MachineDto,
  supervisor: StaffDto | null,
): JobFormValues {
  // A job priced by hand (negotiated, or a field request still without a price) keeps a typed rate.
  const unpriced = job.rate_source === PENDING_PRICE;
  const negotiated =
    job.rate_source === 'NEGOTIATED' || job.rate_source === 'OWNER_APPROVED' || unpriced;
  return {
    contract,
    job_number: job.job_number,
    machine,
    job_site_id: job.job_site_id ?? '',
    supervisor,
    planned_start: job.planned_start,
    planned_end: job.planned_end ?? '',
    rate_mode: negotiated ? 'NEGOTIATED' : 'RATE_CARD',
    hourly_rate: negotiated && !unpriced ? job.hourly_rate : '',
    minimum_hours: negotiated && !unpriced ? job.minimum_hours : '',
    standby_treatment: job.standby_treatment,
    standby_rate: job.standby_rate ?? '',
    mobilization_fee: job.mobilization_fee,
    discount_percent: job.discount_percent,
    tax_rate_percent: job.tax_rate_percent,
    billing_mode: job.billing_mode,
  };
}

/** PUT body: the create payload without contract and job number, plus the version read. */
export function toJobUpdatePayload(v: JobFormValues, version: number): JobUpdateIn {
  const p = toJobPayload(v);
  return {
    machine_id: p.machine_id,
    job_site_id: p.job_site_id ?? null,
    supervisor_id: p.supervisor_id ?? null,
    planned_start: p.planned_start,
    planned_end: p.planned_end ?? null,
    hourly_rate: p.hourly_rate ?? null,
    minimum_hours: p.minimum_hours ?? null,
    standby_treatment: p.standby_treatment,
    standby_rate: p.standby_rate ?? null,
    mobilization_fee: p.mobilization_fee,
    discount_percent: p.discount_percent,
    tax_rate_percent: p.tax_rate_percent,
    billing_mode: p.billing_mode ?? null,
    version,
  };
}
