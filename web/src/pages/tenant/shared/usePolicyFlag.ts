import { useCallback } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { policyService } from '../../../api/services/policyService';
import type { PolicyType } from '../../../api/types';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useSession } from '../../../session/useSession';

/**
 * One boolean of a tenant policy, true only when the policy says so; off while unknown (the user may
 * not read it, or it is still loading) and the server enforces the rule anyway. `extraReaders` lists
 * the capture permissions the API also lets read that policy.
 */
export function usePolicyFlag(
  type: PolicyType,
  key: string,
  extraReaders: readonly string[] = [],
): boolean {
  const { hasPermission } = useSession();
  const canRead = hasPermission([PERMISSIONS.tenantPolicyRead, ...extraReaders], 'any');
  const load = useCallback(
    async (signal: AbortSignal) => (await policyService.effective(type, {}, signal)).values,
    [type],
  );
  return useAsyncResource(load, [type], canRead).data?.[key] === true;
}
