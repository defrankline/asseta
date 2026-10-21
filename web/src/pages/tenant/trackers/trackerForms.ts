import { boolean, mixed, object, string } from 'yup';
import type { ProvisioningState } from '../../../api/types';
import { labelOf, TRACKER_STATE_OPTIONS, type Option } from '../shared/display';

/** Allowed provisioning transitions (mirrors the backend; the API remains authoritative). */
export const STATE_TRANSITIONS: Readonly<Record<ProvisioningState, readonly ProvisioningState[]>> =
  {
    REGISTERED: ['SUSPENDED', 'RETIRED'],
    VERIFIED_REPORTING: ['SUSPENDED', 'RETIRED'],
    SUSPENDED: ['REGISTERED', 'RETIRED'],
    RETIRED: [],
  };

const ACTION_LABELS: Readonly<Partial<Record<ProvisioningState, string>>> = {
  SUSPENDED: 'Suspend',
  RETIRED: 'Retire (permanent)',
  REGISTERED: 'Reactivate',
};

function targetOptions(current: ProvisioningState): readonly Option<ProvisioningState>[] {
  return STATE_TRANSITIONS[current].map((s) => ({
    value: s,
    label: `${ACTION_LABELS[s] ?? labelOf(TRACKER_STATE_OPTIONS, s)} → ${labelOf(TRACKER_STATE_OPTIONS, s)}`,
  }));
}

/** Static select options per current state (the allowed transitions). */
export const STATE_TARGET_OPTIONS: Readonly<
  Record<ProvisioningState, readonly Option<ProvisioningState>[]>
> = {
  REGISTERED: targetOptions('REGISTERED'),
  VERIFIED_REPORTING: targetOptions('VERIFIED_REPORTING'),
  SUSPENDED: targetOptions('SUSPENDED'),
  RETIRED: targetOptions('RETIRED'),
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

export interface StateValues {
  state: ProvisioningState | '';
  reason: string;
}

export const stateSchema = object({
  state: mixed<ProvisioningState | ''>()
    .required('Choose a new state')
    .test('chosen', 'Choose a new state', (v) => v !== ''),
  reason: reasonSchema(true),
});

/** Trimmed text or null (optional API strings). */
export function orNull(value: string): string | null {
  const t = value.trim();
  return t === '' ? null : t;
}
