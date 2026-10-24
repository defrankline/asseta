import { useHoursPolicy } from '../hours/useHoursPolicy';
import type { BillingChoice } from './JobFormSteps';

/** Billing modes offered on job forms: only when the tenant's CUSTOMER_HOURS policy is known and on. */
export function useBillingChoice(): BillingChoice | null {
  const { status, policy } = useHoursPolicy();
  if (status !== 'known' || policy === null || !policy.enabled) return null;
  return { modes: policy.billingModes, defaultMode: policy.defaultBillingMode };
}
