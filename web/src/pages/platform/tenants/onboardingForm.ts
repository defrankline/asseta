import { object, string } from 'yup';
import type { TenantOnboardIn } from '../../../api/types';
import {
  RATE_POLICY_FIELDS,
  RATE_PRICE_FIELDS,
  RATE_TERM_DEFAULTS,
  rateTermsShape,
  toRateTermsIn,
  withPrefix,
  type RateTermsValues,
} from '../shared/rateTerms';
import { integerField, isoDateField } from '../shared/validators';

/**
 * Onboarding form values. The shape mirrors TenantOnboardIn so server `details[].field` paths
 * (e.g. `owner.email`, `subscription.rate.unit_price`) map straight onto Formik fields.
 */
export interface OnboardingValues {
  legal_name: string;
  display_name: string;
  registration_number: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  timezone: string;
  currency: string;
  locale: string;
  owner: { email: string; first_name: string; last_name: string };
  subscription: {
    start_date: string;
    trial_days: string;
    payment_terms_days: string;
    rate: RateTermsValues;
  };
}

export const DEFAULT_TIMEZONE = 'Africa/Dar_es_Salaam';

export function initialOnboardingValues(today: string): OnboardingValues {
  return {
    legal_name: '',
    display_name: '',
    registration_number: '',
    contact_name: '',
    contact_email: '',
    contact_phone: '',
    timezone: DEFAULT_TIMEZONE,
    currency: 'TZS',
    locale: 'en',
    owner: { email: '', first_name: '', last_name: '' },
    subscription: {
      start_date: today,
      trial_days: '0',
      payment_terms_days: '14',
      rate: { ...RATE_TERM_DEFAULTS },
    },
  };
}

const FALLBACK_ZONES = [
  DEFAULT_TIMEZONE,
  'Africa/Nairobi',
  'Africa/Kampala',
  'Africa/Kigali',
  'UTC',
];

/** IANA zones known to the browser (falls back to a short regional list). */
export function timezoneOptions(): readonly string[] {
  try {
    const zones = Intl.supportedValuesOf('timeZone');
    return zones.includes(DEFAULT_TIMEZONE) ? zones : [DEFAULT_TIMEZONE, ...zones];
  } catch {
    return FALLBACK_ZONES;
  }
}

const zoneSet = new Set(timezoneOptions());

const text = (label: string, min: number, max: number) =>
  string()
    .trim()
    .required(`${label} is required`)
    .min(min, `${label} must be at least ${String(min)} characters`)
    .max(max, `${label} must be at most ${String(max)} characters`);

const email = (label: string) =>
  string().trim().required(`${label} is required`).email('Enter a valid email address');

/** Mirrors TenantOnboardIn / OwnerIn / SubscriptionSetupIn / RateTermsIn constraints. */
export const onboardingSchema = object({
  legal_name: text('Legal name', 2, 200),
  display_name: text('Display name', 2, 120),
  registration_number: string().trim().max(64, 'At most 64 characters').default(''),
  contact_name: text('Contact name', 2, 200),
  contact_email: email('Contact email'),
  contact_phone: string().trim().max(40, 'At most 40 characters').default(''),
  timezone: string()
    .required('Timezone is required')
    .test('iana', 'Choose a valid IANA timezone', (v) => zoneSet.has(v)),
  currency: string()
    .required('Currency is required')
    .matches(/^[A-Z]{3}$/, 'Use a 3-letter ISO currency code'),
  locale: string().trim().required('Locale is required').max(16, 'At most 16 characters'),
  owner: object({
    email: email('Owner email'),
    first_name: text('First name', 1, 100),
    last_name: text('Last name', 1, 100),
  }),
  subscription: object({
    start_date: isoDateField('Start date'),
    trial_days: integerField('Trial days', 0, 365),
    payment_terms_days: integerField('Payment terms', 0, 180),
    rate: object(rateTermsShape),
  }),
});

export const COMPANY_FIELDS = [
  'legal_name',
  'display_name',
  'registration_number',
  'contact_name',
  'contact_email',
  'contact_phone',
] as const;
export const SETTINGS_FIELDS = ['timezone', 'currency', 'locale'] as const;
export const OWNER_FIELDS = ['owner.email', 'owner.first_name', 'owner.last_name'] as const;
export const COMMERCIAL_FIELDS = [
  'subscription.start_date',
  'subscription.trial_days',
  'subscription.payment_terms_days',
  ...withPrefix('subscription.rate.', RATE_PRICE_FIELDS),
  ...withPrefix('subscription.rate.', RATE_POLICY_FIELDS),
];

const optional = (v: string): string | null => (v.trim() === '' ? null : v.trim());

export function toOnboardPayload(v: OnboardingValues): TenantOnboardIn {
  return {
    legal_name: v.legal_name.trim(),
    display_name: v.display_name.trim(),
    registration_number: optional(v.registration_number),
    contact_name: v.contact_name.trim(),
    contact_email: v.contact_email.trim(),
    contact_phone: optional(v.contact_phone),
    timezone: v.timezone,
    currency: v.currency,
    locale: v.locale.trim(),
    owner: {
      email: v.owner.email.trim(),
      first_name: v.owner.first_name.trim(),
      last_name: v.owner.last_name.trim(),
    },
    subscription: {
      start_date: v.subscription.start_date,
      trial_days: Number(v.subscription.trial_days),
      payment_terms_days: Number(v.subscription.payment_terms_days),
      rate: toRateTermsIn(v.subscription.rate),
    },
  };
}
