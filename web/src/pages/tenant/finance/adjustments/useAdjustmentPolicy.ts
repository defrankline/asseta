import { useCallback } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { policyService } from '../../../../api/services/policyService';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useSession } from '../../../../session/useSession';

export interface AdjustmentPolicy {
  /** False while unknown: the user may not read the policy and the server still enforces it. */
  known: boolean;
  evidenceRequired: boolean;
  reasonCodeRequired: boolean;
  /** RECEIVABLE or CASE; null while unknown. */
  usedHoursTreatment: string | null;
}

const UNKNOWN: AdjustmentPolicy = {
  known: false,
  evidenceRequired: false,
  reasonCodeRequired: false,
  usedHoursTreatment: null,
};

/** The tenant's CUSTOMER_HOURS rules for corrections, refunds and reversals (read when a form opens). */
export function useAdjustmentPolicy(): AdjustmentPolicy {
  const { hasPermission } = useSession();
  const canRead = hasPermission(
    [PERMISSIONS.tenantPolicyRead, PERMISSIONS.tenantHoursPurchase],
    'any',
  );
  const load = useCallback(
    async (signal: AbortSignal) =>
      (await policyService.effective('CUSTOMER_HOURS', {}, signal)).values,
    [],
  );
  const res = useAsyncResource(load, [], canRead);
  if (res.data === null) return UNKNOWN;
  const v = res.data;
  return {
    known: true,
    evidenceRequired: v.adjustment_evidence_required !== false,
    reasonCodeRequired: v.reason_code_required === true,
    usedHoursTreatment:
      typeof v.reversal_used_hours_treatment === 'string' ? v.reversal_used_hours_treatment : null,
  };
}
