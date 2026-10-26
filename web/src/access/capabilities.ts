import { useContext, useMemo } from 'react';
import type { RecordKind } from '../navigation/recordRoutes';
import { SessionContext } from '../session/SessionContext';

/**
 * Tenant capabilities a policy can switch off (`/me` tenants[].disabled_capabilities). Menus for a
 * disabled capability are already omitted by the server (CASH_CUSTODY keeps its menus: they hold
 * the cash basics); these gate everything else on the web.
 */
export const CAPABILITY = {
  customerHours: 'CUSTOMER_HOURS',
  engineHours: 'ENGINE_HOURS',
  cashCustody: 'CASH_CUSTODY',
  revenue: 'REVENUE_RECONCILIATION',
} as const;

export type CapabilityCode = (typeof CAPABILITY)[keyof typeof CAPABILITY];

/** The plain feature name of each capability, for the "not enabled" state. */
export const CAPABILITY_FEATURE: Readonly<Record<CapabilityCode, string>> = {
  CUSTOMER_HOURS: 'Customer hours',
  ENGINE_HOURS: 'Engine hours',
  CASH_CUSTODY: 'This cash custody control',
  REVENUE_RECONCILIATION: 'Revenue checks',
};

/** The capability each exact-record kind belongs to (cash floats and remittances are the basics). */
export const RECORD_KIND_CAPABILITY: Readonly<Partial<Record<RecordKind, CapabilityCode>>> = {
  HOURS_DISCOUNT: CAPABILITY.customerHours,
  HOURS_CREDIT: CAPABILITY.customerHours,
  HOURS_TRANSFER: CAPABILITY.customerHours,
  HOURS_CANCELLATION: CAPABILITY.customerHours,
  METER_BASELINE: CAPABILITY.engineHours,
  METER_CORRECTION: CAPABILITY.engineHours,
  ENGINE_HOURS_CLASSIFICATION: CAPABILITY.engineHours,
  CASH_TRANSFER: CAPABILITY.cashCustody,
  CASH_VARIANCE: CAPABILITY.cashCustody,
  CASH_RETENTION: CAPABILITY.cashCustody,
  CUSTODY_ADJUSTMENT: CAPABILITY.cashCustody,
  REMITTANCE_OVERDUE: CAPABILITY.cashCustody,
  REVENUE_DIFFERENCE: CAPABILITY.revenue,
  NON_REVENUE_APPROVAL: CAPABILITY.revenue,
};

/** Page path prefixes owned by a capability (direct links fall back when it is off). */
const PATH_CAPABILITY: readonly [string, CapabilityCode][] = [
  ['/tenant/hours/', CAPABILITY.customerHours],
  // Before the engine-hours prefix: the daily machine sheet belongs to revenue checks.
  ['/tenant/engine-hours/daily-sheet', CAPABILITY.revenue],
  ['/tenant/revenue-differences', CAPABILITY.revenue],
  ['/tenant/revenue-reasons', CAPABILITY.revenue],
  ['/tenant/non-revenue-approvals', CAPABILITY.revenue],
  ['/tenant/engine-hours', CAPABILITY.engineHours],
  ['/tenant/meter-baselines', CAPABILITY.engineHours],
  ['/tenant/meter-corrections', CAPABILITY.engineHours],
  ['/tenant/engine-hour-reasons', CAPABILITY.engineHours],
  ['/tenant/finance/cash/transfers', CAPABILITY.cashCustody],
  ['/tenant/finance/cash/variances', CAPABILITY.cashCustody],
  ['/tenant/finance/cash/retentions', CAPABILITY.cashCustody],
  ['/tenant/finance/cash/adjustments', CAPABILITY.cashCustody],
  ['/tenant/finance/cash/remittance-overdue', CAPABILITY.cashCustody],
];

/** The capability that owns a console path, or null. */
export function pathCapability(path: string): CapabilityCode | null {
  const base = path.split('?')[0] ?? path;
  return PATH_CAPABILITY.find(([prefix]) => base.startsWith(prefix))?.[1] ?? null;
}

/** Capabilities the active tenant's effective policy switches off (none outside a session). */
export function useDisabledCapabilities(): ReadonlySet<string> {
  const list = useContext(SessionContext)?.activeTenant?.disabled_capabilities;
  return useMemo(() => new Set(list ?? []), [list]);
}

/** False when the active tenant's effective policy switches the capability off. */
export function useCapabilityEnabled(capability: CapabilityCode): boolean {
  return !useDisabledCapabilities().has(capability);
}
