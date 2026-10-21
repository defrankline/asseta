import { boolean, mixed, object, string, type ObjectSchema } from 'yup';
import { STAFF_KINDS } from '../../../api/services/fleetSchemas';
import type { StaffDto, StaffIn, StaffKind, StaffUpdateIn } from '../../../api/types';

export interface StaffFormValues {
  full_name: string;
  kind: StaffKind;
  employee_code: string;
  phone: string;
  keycloak_subject: string;
  is_active: boolean;
}

const opt = (label: string, max: number) =>
  string()
    .trim()
    .max(max, `${label} must be at most ${String(max)} characters`)
    .ensure();

export const staffSchema: ObjectSchema<StaffFormValues> = object({
  full_name: string()
    .trim()
    .required('Full name is required')
    .max(200, 'Full name must be at most 200 characters'),
  kind: mixed<StaffKind>().oneOf(STAFF_KINDS).required('Kind is required'),
  employee_code: opt('Employee code', 40),
  phone: opt('Phone', 40),
  keycloak_subject: opt('Login subject', 64),
  is_active: boolean().required(),
});

const orNull = (v: string) => (v.trim() === '' ? null : v.trim());

export function toStaffPayload(v: StaffFormValues): StaffIn {
  return {
    full_name: v.full_name.trim(),
    kind: v.kind,
    employee_code: orNull(v.employee_code),
    phone: orNull(v.phone),
    keycloak_subject: orNull(v.keycloak_subject),
    is_active: v.is_active,
  };
}

export function valuesFromStaff(s: StaffDto): StaffFormValues {
  return {
    full_name: s.full_name,
    kind: s.kind,
    employee_code: s.employee_code ?? '',
    phone: s.phone ?? '',
    keycloak_subject: s.keycloak_subject ?? '',
    is_active: s.is_active,
  };
}

/** PUT body: identity and login link; activity changes go through deactivate / reactivate. */
export function toStaffUpdatePayload(v: StaffFormValues, version: number): StaffUpdateIn {
  return {
    full_name: v.full_name.trim(),
    kind: v.kind,
    employee_code: orNull(v.employee_code),
    phone: orNull(v.phone),
    keycloak_subject: orNull(v.keycloak_subject),
    version,
  };
}

/** Stable staff error codes with what the user can do about them. */
export const STAFF_ERROR_HINTS: Readonly<Record<string, string>> = {
  STAFF_HAS_ACTIVE_JOBS: 'Reassign or finish the jobs this person supervises first.',
  STAFF_HOLDS_CASH: 'Record a cash handover so this person holds no cash first.',
  STAFF_ASSIGNED: 'End this person’s machine assignments before changing their kind.',
  DUPLICATE_STAFF: 'Another staff member already uses this employee code or login.',
};

export const STAFF_DEACTIVATE_CONSEQUENCES =
  'Their open machine assignments are ended, and they can no longer be assigned to machines or jobs.';

export const PERSON_FIELDS = ['full_name', 'kind', 'employee_code', 'phone'] as const;
