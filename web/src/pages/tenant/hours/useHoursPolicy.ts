import { useCallback } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import type { BillingMode } from '../../../api/hoursTypes';
import { policyService } from '../../../api/services/policyService';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useSession } from '../../../session/useSession';

/** The tenant's effective CUSTOMER_HOURS policy, as the screens need it (never hard-coded). */
export interface HoursPolicy {
  enabled: boolean;
  walkInAllowed: boolean;
  billingModes: readonly BillingMode[];
  defaultBillingMode: BillingMode;
  /** VERIFIED_PAYMENT and/or CREDIT. */
  activationBasis: readonly string[];
  creditAllowed: boolean;
  discountRequiresApproval: boolean;
  transferRequiresApproval: boolean;
  cancellationRequiresApproval: boolean;
  reasonCodeRequired: boolean;
  maxDiscountPercent: string;
}

const MODES: readonly BillingMode[] = ['INVOICE', 'PREPAID_HOURS'];
const isMode = (v: unknown): v is BillingMode => MODES.includes(v as BillingMode);

const flag = (v: unknown, fallback: boolean): boolean => (typeof v === 'boolean' ? v : fallback);
const list = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [];

/** Policy `values` (free-form JSON) → typed view; missing keys fall back to "off". */
export function parseHoursPolicy(values: Record<string, unknown>): HoursPolicy {
  const modes = list(values.billing_modes).filter(isMode);
  const def = values.default_billing_mode;
  return {
    enabled: flag(values.enabled, false),
    walkInAllowed: flag(values.walk_in_allowed, false),
    billingModes: modes,
    defaultBillingMode: isMode(def) ? def : 'INVOICE',
    activationBasis: list(values.activation_basis),
    creditAllowed: flag(values.credit_allowed, false),
    discountRequiresApproval: flag(values.discount_requires_approval, true),
    transferRequiresApproval: flag(values.transfer_requires_approval, true),
    cancellationRequiresApproval: flag(values.cancellation_requires_approval, true),
    reasonCodeRequired: flag(values.reason_code_required, false),
    maxDiscountPercent:
      typeof values.max_discount_percent === 'string' ? values.max_discount_percent : '100',
  };
}

export interface HoursPolicyState {
  /** `unknown`: the user may not read the policy; the server still enforces it on every action. */
  status: 'loading' | 'known' | 'unknown';
  policy: HoursPolicy | null;
  /** Capability on (known and enabled), or not readable (server decides). False while loading. */
  on: boolean;
}

/**
 * Reads the effective CUSTOMER_HOURS policy (policy readers and hours recorders may read it). Screens
 * show hours actions only when `on`; when the capability is off they behave exactly as before.
 */
export function useHoursPolicy(): HoursPolicyState {
  const { hasPermission } = useSession();
  const canRead = hasPermission(
    [PERMISSIONS.tenantPolicyRead, PERMISSIONS.tenantHoursPurchase],
    'any',
  );
  const load = useCallback(
    async (signal: AbortSignal) =>
      parseHoursPolicy((await policyService.effective('CUSTOMER_HOURS', {}, signal)).values),
    [],
  );
  const res = useAsyncResource(load, [], canRead);
  if (!canRead || res.error !== null) return { status: 'unknown', policy: null, on: true };
  if (res.data === null) return { status: 'loading', policy: null, on: false };
  return { status: 'known', policy: res.data, on: res.data.enabled };
}
