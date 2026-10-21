import { object, string, type ObjectSchema } from 'yup';
import type { TenantDto, TenantUpdateIn } from '../../../api/types';

/** Company details editable after onboarding (currency and timezone are fixed). */
export interface TenantEditValues {
  legal_name: string;
  display_name: string;
  registration_number: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
}

export const COMPANY_EDIT_FIELDS = ['legal_name', 'display_name', 'registration_number'] as const;
export const CONTACT_EDIT_FIELDS = ['contact_name', 'contact_email', 'contact_phone'] as const;

export const TENANT_ERROR_HINTS: Readonly<Record<string, string>> = {
  TENANT_VERIFIED_FIELD: 'The registration number is fixed once the company is verified.',
  TENANT_EXISTS: 'Another tenant already uses this name or registration number.',
  TENANT_CLOSED: 'A closed tenant is read-only.',
};

/** CLOSED tenants are read-only. */
export const canEditTenant = (t: TenantDto) => t.status !== 'CLOSED';

/** Registration number is fixed once the company is verified. */
export const registrationLocked = (t: TenantDto) => t.verification_status === 'VERIFIED';

export function valuesFromTenant(t: TenantDto): TenantEditValues {
  return {
    legal_name: t.legal_name,
    display_name: t.display_name,
    registration_number: t.registration_number ?? '',
    contact_name: t.contact_name,
    contact_email: t.contact_email,
    contact_phone: t.contact_phone ?? '',
  };
}

const text = (label: string, min: number, max: number) =>
  string()
    .trim()
    .required(`${label} is required`)
    .min(min, `${label} must be at least ${String(min)} characters`)
    .max(max, `${label} must be at most ${String(max)} characters`);

/** Mirrors TenantUpdateIn constraints. */
export const tenantEditSchema: ObjectSchema<TenantEditValues> = object({
  legal_name: text('Legal name', 2, 200),
  display_name: text('Display name', 2, 120),
  registration_number: string().trim().max(64, 'At most 64 characters').ensure(),
  contact_name: text('Contact name', 2, 200),
  contact_email: string()
    .trim()
    .required('Contact email is required')
    .email('Enter a valid email address'),
  contact_phone: string().trim().max(40, 'At most 40 characters').ensure(),
});

const orNull = (v: string): string | null => (v.trim() === '' ? null : v.trim());

export function toTenantUpdate(v: TenantEditValues, version: number): TenantUpdateIn {
  return {
    legal_name: v.legal_name.trim(),
    display_name: v.display_name.trim(),
    registration_number: orNull(v.registration_number),
    contact_name: v.contact_name.trim(),
    contact_email: v.contact_email.trim(),
    contact_phone: orNull(v.contact_phone),
    version,
  };
}
