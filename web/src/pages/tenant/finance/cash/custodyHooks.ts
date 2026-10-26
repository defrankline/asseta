import { useCallback, useMemo } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { custodyService } from '../../../../api/services/custodyService';
import { policyService } from '../../../../api/services/policyService';
import type { CustodianDto } from '../../../../api/custodyTypes';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useSession } from '../../../../session/useSession';
import { shortId } from '../../shared/financeDisplay';
import { remittanceRequirements, type RemittanceRequirements } from './cashForms';

/** The tenant's effective CASH_CUSTODY policy as the screens need it (never hard-coded). */
export interface CashPolicy {
  recordersMayRecordForOthers: boolean;
  transferAckRequired: boolean;
  recorderReceiverCountsAsAck: boolean;
  floatAckRequired: boolean;
  remitFullBalance: boolean;
  writeoffRequiresApproval: boolean;
  retentionAllowed: boolean;
  /** What a remittance must carry (DEC-031 D2); all off while the cash custody controls are off. */
  remittance: RemittanceRequirements;
}

const flag = (v: unknown, fallback: boolean): boolean => (typeof v === 'boolean' ? v : fallback);

/** Policy `values` (free-form JSON) → typed view. */
export function parseCashPolicy(values: Record<string, unknown>): CashPolicy {
  return {
    recordersMayRecordForOthers: flag(values.recorders_may_record_for_others, false),
    transferAckRequired: flag(values.transfer_ack_required, true),
    recorderReceiverCountsAsAck: flag(values.recorder_receiver_counts_as_ack, true),
    floatAckRequired: flag(values.float_ack_required, false),
    remitFullBalance: flag(values.remit_full_balance, true),
    writeoffRequiresApproval: flag(values.writeoff_requires_approval, true),
    retentionAllowed: flag(values.retention_allowed, false),
    remittance: remittanceRequirements(values),
  };
}

/**
 * The effective CASH_CUSTODY policy, or null when the user may not read it (or it failed to load):
 * screens then show the permission-gated actions and the server applies the policy.
 */
export function useCashPolicy(): CashPolicy | null {
  const { hasPermission } = useSession();
  const canRead = hasPermission(
    [PERMISSIONS.tenantPolicyRead, PERMISSIONS.tenantCollectionRecord],
    'any',
  );
  const load = useCallback(
    async (signal: AbortSignal) =>
      parseCashPolicy((await policyService.effective('CASH_CUSTODY', {}, signal)).values),
    [],
  );
  const res = useAsyncResource(load, [], canRead);
  return canRead ? res.data : null;
}

/** Whoever may see custody: field recorders (own / on behalf) and finance readers. */
const CUSTODY_READERS = [PERMISSIONS.tenantCollectionRecord, PERMISSIONS.tenantFinanceRead];

export const custodianLabel = (c: CustodianDto): string =>
  c.employee_code === null ? c.full_name : `${c.full_name} (${c.employee_code})`;
export const custodianId = (c: CustodianDto): string => c.staff_member_id;

export const searchCustodians = async (q: string, signal: AbortSignal) =>
  (await custodyService.custodians({ page: 1, page_size: 20, q }, signal)).items;

/** No get-by-id endpoint: read the list (inactive included) and pick the id. */
export const resolveCustodian = async (id: string, signal: AbortSignal) =>
  (
    await custodyService.custodians(
      { page: 1, page_size: 200, filters: { include_inactive: 'true' } },
      signal,
    )
  ).items.find((c) => c.staff_member_id === id) ?? null;

/** Staff id → custodian name for list displays (first 200, inactive included). */
export function useCustodianLabels(): (id: string | null) => string {
  const { hasPermission } = useSession();
  const load = useCallback(
    async (signal: AbortSignal) =>
      (
        await custodyService.custodians(
          { page: 1, page_size: 200, filters: { include_inactive: 'true' } },
          signal,
        )
      ).items,
    [],
  );
  const res = useAsyncResource(load, [], hasPermission(CUSTODY_READERS, 'any'));
  return useMemo(() => {
    const names = new Map((res.data ?? []).map((c) => [c.staff_member_id, c.full_name]));
    return (id: string | null) => (id === null ? '—' : (names.get(id) ?? shortId(id)));
  }, [res.data]);
}
