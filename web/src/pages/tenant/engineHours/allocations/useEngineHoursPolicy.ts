import { useCallback } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { policyService } from '../../../../api/services/policyService';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useSession } from '../../../../session/useSession';

export interface EngineHoursRules {
  /** The next job must be named on a changeover. */
  changeoverJobRequired: boolean;
  /** A daily report needs at least one photo. */
  reportEvidenceRequired: boolean;
}

/**
 * The ENGINE_HOURS rules a field form enforces up front, for one machine (null until chosen). Until
 * they load, or if they cannot be read, nothing extra is required here and the server still refuses.
 */
export function useEngineHoursRules(
  machineId: string | null,
  siteId: string | null = null,
): EngineHoursRules {
  const { hasPermission } = useSession();
  const canRead = hasPermission(
    [PERMISSIONS.tenantPolicyRead, PERMISSIONS.tenantMeterCapture],
    'any',
  );
  const load = useCallback(
    (signal: AbortSignal) =>
      policyService.effective(
        'ENGINE_HOURS',
        { machine_id: machineId ?? undefined, site_id: siteId ?? undefined },
        signal,
      ),
    [machineId, siteId],
  );
  const res = useAsyncResource(load, [machineId, siteId], canRead && machineId !== null);
  const values = res.data?.values;
  return {
    changeoverJobRequired: values?.changeover_splits_billing === true,
    reportEvidenceRequired: values?.daily_report_evidence_required === true,
  };
}
