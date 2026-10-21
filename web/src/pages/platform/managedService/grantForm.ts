import { mixed, object, string, type ObjectSchema } from 'yup';
import { MANDATE_SCOPES } from '../../../api/services/mandateSchemas';
import type { MandateGrantIn, MandateScope } from '../../../api/types';
import type { SelectOption } from '../../../components/forms/FormikSelectField';
import { isIsoDate } from '../../../utils/dates';
import { isoDateField } from '../shared/validators';

export interface GrantFormValues {
  tenant_id: string;
  scope: MandateScope;
  starts_on: string;
  /** '' = open-ended (until ended or revoked). */
  ends_on: string;
  consent_reference: string;
  notes: string;
}

export const SCOPE_OPTIONS: readonly SelectOption[] = [
  { value: 'FULL', label: 'Full management' },
  { value: 'OPERATIONS', label: 'Operations only' },
];

export const grantSchema: ObjectSchema<GrantFormValues> = object({
  tenant_id: string().required('Client is required'),
  scope: mixed<MandateScope>().oneOf(MANDATE_SCOPES).required('Scope is required'),
  starts_on: isoDateField('Start date'),
  ends_on: string()
    .ensure()
    .test('iso-date', 'End date must be a valid date', (v) => v === '' || isIsoDate(v))
    .test('after-start', 'End date cannot be before the start date', function check(v) {
      const start = (this.parent as GrantFormValues).starts_on;
      // ISO dates compare correctly as strings.
      return v === '' || !isIsoDate(start) || v >= start;
    }),
  consent_reference: string()
    .trim()
    .required('Consent reference is required')
    .min(2, 'Consent reference must be at least 2 characters')
    .max(160, 'Consent reference must be at most 160 characters'),
  notes: string().trim().max(2000, 'Notes must be at most 2000 characters').ensure(),
});

export function toGrantBody(v: GrantFormValues): MandateGrantIn {
  return {
    tenant_id: v.tenant_id,
    scope: v.scope,
    starts_on: v.starts_on,
    ends_on: v.ends_on === '' ? null : v.ends_on,
    consent_reference: v.consent_reference.trim(),
    notes: v.notes.trim(),
  };
}
