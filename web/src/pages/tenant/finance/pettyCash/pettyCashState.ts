import { useCallback, useMemo } from 'react';
import { CAPABILITY, useCapabilityEnabled } from '../../../../access/capabilities';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import type { PettyCashFundDto } from '../../../../api/pettyCashTypes';
import { pettyCashService } from '../../../../api/services/pettyCashService';
import { policyService } from '../../../../api/services/policyService';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useSession } from '../../../../session/useSession';

/** The tenant's effective PETTY_CASH policy as the screens need it (never hard-coded). */
export interface PettyCashPolicy {
  maxExpenseAmount: string | null;
  overspendAllowedOffline: boolean;
  countEveryDays: number | null;
  countWitnessRequired: boolean;
  returnEvidenceRequired: boolean;
  fundingEvidenceRequired: boolean;
  advancesEnabled: boolean;
  advanceClearWithinDays: number;
}

const flag = (v: unknown, fallback: boolean): boolean => (typeof v === 'boolean' ? v : fallback);
const num = (v: unknown): number | null => (typeof v === 'number' ? v : null);
const money = (v: unknown): string | null =>
  typeof v === 'string' ? v : typeof v === 'number' ? String(v) : null;

/** Policy `values` (free-form JSON) → typed view; unknown values fall back to the platform default. */
export function parsePettyCashPolicy(values: Record<string, unknown>): PettyCashPolicy {
  return {
    maxExpenseAmount: money(values.max_expense_amount),
    overspendAllowedOffline: flag(values.overspend_allowed_offline, true),
    countEveryDays: num(values.count_every_days),
    countWitnessRequired: flag(values.count_witness_required, false),
    returnEvidenceRequired: flag(values.return_evidence_required, false),
    fundingEvidenceRequired: flag(values.funding_evidence_required, false),
    advancesEnabled: flag(values.advances_enabled, false),
    advanceClearWithinDays: num(values.advance_clear_within_days) ?? 7,
  };
}

/** True while the tenant's PETTY_CASH capability is on and the user may read petty cash. */
export function usePettyCashOn(): boolean {
  const on = useCapabilityEnabled(CAPABILITY.pettyCash);
  const { hasPermission } = useSession();
  return on && hasPermission(PERMISSIONS.tenantPettyCashRead);
}

/**
 * The effective PETTY_CASH policy, or null while loading, when petty cash is off or the user may not
 * read it: screens then show the permission-gated actions and the server applies the policy.
 */
export function usePettyCashPolicy(): PettyCashPolicy | null {
  const on = usePettyCashOn();
  const load = useCallback(
    async (signal: AbortSignal) =>
      parsePettyCashPolicy((await policyService.effective('PETTY_CASH', {}, signal)).values),
    [],
  );
  const res = useAsyncResource(load, [], on);
  return on ? res.data : null;
}

/** Ids of the active funds the caller holds (holder-only actions; the holder never approves). */
export function useMyFunds(reloadKey = 0): {
  funds: PettyCashFundDto[] | null;
  holds: (fundId: string) => boolean;
  reload: () => void;
} {
  const on = usePettyCashOn();
  const load = useCallback((signal: AbortSignal) => pettyCashService.myFunds(signal), []);
  const res = useAsyncResource(load, [reloadKey], on);
  const ids = useMemo(() => new Set((res.data ?? []).map((f) => f.id)), [res.data]);
  const holds = useCallback((fundId: string) => ids.has(fundId), [ids]);
  return { funds: on ? res.data : [], holds, reload: res.reload };
}

export const fundLabel = (f: Pick<PettyCashFundDto, 'code' | 'name'>): string =>
  `${f.code} · ${f.name}`;

/** Fund search (code / name), active funds only unless `includeInactive`. */
export const searchFunds = async (q: string, signal: AbortSignal, includeInactive = false) =>
  (
    await pettyCashService.funds(
      {
        page: 1,
        page_size: 20,
        q,
        filters: {
          with_balance: 'false',
          include_inactive: includeInactive ? 'true' : undefined,
        },
      },
      signal,
    )
  ).items;
