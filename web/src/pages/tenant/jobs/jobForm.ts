import { mixed, object, string, type ObjectSchema } from 'yup';
import type {
  ContractDto,
  JobIn,
  MachineDto,
  StaffDto,
  StandbyTreatment,
} from '../../../api/types';
import { STANDBY_TREATMENTS } from '../../../api/services/jobSchemas';
import {
  isAfter,
  optionalDecimal,
  optionalInstant,
  orNull,
  percentDecimal,
  requiredDecimal,
  requiredInstant,
} from '../shared/formRules';

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
  };
}
