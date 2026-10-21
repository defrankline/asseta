import { boolean, mixed, object, string, type ObjectSchema } from 'yup';
import { STAFF_KINDS } from '../../../api/services/fleetSchemas';
import type { StaffIn, StaffKind } from '../../../api/types';

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
