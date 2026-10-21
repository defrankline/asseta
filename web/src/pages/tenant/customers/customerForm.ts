import { object, string, type ObjectSchema } from 'yup';
import type { CustomerDto, CustomerIn, CustomerUpdateIn } from '../../../api/types';
import { optionalText, orNull } from '../shared/formRules';

/** Field names equal API names so server `details[].field` errors land on the right input. */
export interface CustomerFormValues {
  code: string;
  name: string;
  tax_id: string;
  payment_terms_days: string;
  contact_name: string;
  contact_phone: string;
  contact_email: string;
}

export const CUSTOMER_FIELDS = ['code', 'name', 'tax_id', 'payment_terms_days'] as const;
export const CONTACT_FIELDS = ['contact_name', 'contact_phone', 'contact_email'] as const;

export function emptyCustomerValues(): CustomerFormValues {
  return {
    code: '',
    name: '',
    tax_id: '',
    payment_terms_days: '30',
    contact_name: '',
    contact_phone: '',
    contact_email: '',
  };
}

export const customerFormSchema: ObjectSchema<CustomerFormValues> = object({
  code: string().trim().required('Code is required').max(32, 'Code must be at most 32 characters'),
  name: string()
    .trim()
    .required('Name is required')
    .max(200, 'Name must be at most 200 characters'),
  tax_id: optionalText('Tax ID', 64),
  payment_terms_days: string()
    .trim()
    .required('Payment terms are required')
    .test(
      'days',
      'Payment terms must be a whole number of days between 0 and 365',
      (v) => /^\d{1,3}$/.test(v) && Number(v) <= 365,
    ),
  contact_name: optionalText('Contact name', 200),
  contact_phone: optionalText('Contact phone', 40),
  contact_email: optionalText('Contact email', 320).email('Enter a valid email address'),
});

export function toCustomerPayload(v: CustomerFormValues): CustomerIn {
  return {
    code: v.code.trim(),
    name: v.name.trim(),
    tax_id: orNull(v.tax_id),
    payment_terms_days: Number(v.payment_terms_days),
    contact_name: orNull(v.contact_name),
    contact_phone: orNull(v.contact_phone),
    contact_email: orNull(v.contact_email),
  };
}

export function valuesFromCustomer(c: CustomerDto): CustomerFormValues {
  return {
    code: c.code,
    name: c.name,
    tax_id: c.tax_id ?? '',
    payment_terms_days: String(c.payment_terms_days),
    contact_name: c.contact_name ?? '',
    contact_phone: c.contact_phone ?? '',
    contact_email: c.contact_email ?? '',
  };
}

/** PUT body: every editable field plus the `version` that was read. */
export function toCustomerUpdatePayload(v: CustomerFormValues, version: number): CustomerUpdateIn {
  return { ...toCustomerPayload(v), version };
}
