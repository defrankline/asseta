import { boolean, object, string } from 'yup';
import type { ProvisioningState } from '../../../api/types';

/** Allowed provisioning transitions (mirrors the backend; the API remains authoritative). */
export const STATE_TRANSITIONS: Readonly<Record<ProvisioningState, readonly ProvisioningState[]>> =
  {
    REGISTERED: ['SUSPENDED', 'RETIRED'],
    VERIFIED_REPORTING: ['SUSPENDED', 'RETIRED'],
    SUSPENDED: ['REGISTERED', 'RETIRED'],
    RETIRED: [],
  };

export const reasonSchema = (required: boolean) => {
  const base = string().trim().max(500, 'Reason must be at most 500 characters');
  return required
    ? base.required('Reason is required').min(3, 'Reason must be at least 3 characters')
    : base.default(''); // Formik submits '' as undefined
};

export const instantSchema = (label: string) =>
  string()
    .required(`${label} is required`)
    .test('iso', `${label} must be a valid date and time`, (v) => !Number.isNaN(Date.parse(v)));

export interface AssignValues {
  machine_id: string;
  machine_label: string;
  is_primary: boolean;
  effective_from: string;
  replace_existing_primary: boolean;
  reason: string;
}

export const assignSchema = object({
  machine_id: string().required('Select a machine'),
  machine_label: string().default(''),
  is_primary: boolean().required(),
  effective_from: instantSchema('Effective from'),
  replace_existing_primary: boolean().required(),
  reason: reasonSchema(false),
});

/** Trimmed text or null (optional API strings). */
export function orNull(value: string): string | null {
  const t = value.trim();
  return t === '' ? null : t;
}
