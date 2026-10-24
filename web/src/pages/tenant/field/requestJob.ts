import { object, string, type ObjectSchema } from 'yup';
import type { FieldContractDto, JobRequestIn } from '../../../api/types';
import {
  isAfter,
  optionalInstant,
  optionalText,
  orNull,
  requiredInstant,
} from '../shared/formRules';

/**
 * A job requested from the field: what the customer asked for, where and when. The server numbers
 * and prices it (rate card, or the owner sets the price on approval) and sends it for approval.
 */
export interface RequestJobValues {
  contract_id: string;
  machine_id: string;
  job_site_id: string;
  planned_start: string;
  planned_end: string;
  note: string;
}

export const REQUEST_WHAT_FIELDS = ['contract_id', 'machine_id', 'job_site_id'] as const;
export const REQUEST_WHEN_FIELDS = ['planned_start', 'planned_end', 'note'] as const;

export const REQUEST_NOTE_MAX = 1000;

export function emptyRequestValues(now: string): RequestJobValues {
  return {
    contract_id: '',
    machine_id: '',
    job_site_id: '',
    planned_start: now,
    planned_end: '',
    note: '',
  };
}

export const requestJobSchema: ObjectSchema<RequestJobValues> = object({
  contract_id: string().required('Choose the customer contract'),
  machine_id: string().required('Choose a machine'),
  job_site_id: string().ensure(),
  planned_start: requiredInstant('Planned start'),
  planned_end: optionalInstant().test('after', 'Planned end must be after the start', function (v) {
    return isAfter((this.parent as RequestJobValues).planned_start, v);
  }),
  note: optionalText('Note', REQUEST_NOTE_MAX),
});

/** `client_id` is the new job's id: a replay of the same request returns the same job. */
export function toRequestPayload(v: RequestJobValues, clientId: string): JobRequestIn {
  return {
    client_id: clientId,
    contract_id: v.contract_id,
    machine_id: v.machine_id,
    job_site_id: orNull(v.job_site_id),
    planned_start: v.planned_start,
    planned_end: orNull(v.planned_end),
    note: orNull(v.note),
  };
}

/** "Customer — contract" (with the customer's reference when present). */
export const fieldContractLabel = (c: FieldContractDto): string =>
  `${c.customer_name} — ${c.contract_number}${c.reference === null ? '' : ` · ${c.reference}`}`;
