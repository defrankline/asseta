import { useCallback, useMemo } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { machineService } from '../../../api/services/machineService';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useSession } from '../../../session/useSession';
import { machineLabel } from './display';

/** Machine id → `asset code · name` for list displays (first 200 machines; falls back to the id). */
export function useMachineLabels(): (id: string) => string {
  const { hasPermission } = useSession();
  const canRead = hasPermission(PERMISSIONS.tenantMachineRead);
  const load = useCallback(
    (signal: AbortSignal) => machineService.list({ page: 1, page_size: 200 }, signal),
    [],
  );
  const res = useAsyncResource(load, [], canRead);
  return useMemo(() => {
    const names = new Map((res.data?.items ?? []).map((m) => [m.id, machineLabel(m)]));
    return (id: string) => names.get(id) ?? `${id.slice(0, 8)}…`;
  }, [res.data]);
}
