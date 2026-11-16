import { useCallback, useMemo } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { machineService } from '../../../api/services/machineService';
import type { MachineDto } from '../../../api/types';
import { LOOKUP_PAGE_SIZE } from '../../../components/data/AsyncAutocomplete';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useSession } from '../../../session/useSession';
import { machineLabel } from '../shared/display';

/**
 * Field-scoped lookups. A supervisor sees only the machines they work on (`/tenant/field/machines`, no
 * machine register access); office roles search the register. Every search passes the typed text to
 * the API; nothing is filtered in the browser.
 */

export const searchFieldMachines = (q: string, signal: AbortSignal): Promise<MachineDto[]> =>
  machineService.fieldMachines(q.trim() === '' ? undefined : q, signal);

export const resolveFieldMachine = async (
  id: string,
  signal: AbortSignal,
): Promise<MachineDto | null> =>
  (await machineService.fieldMachines(undefined, signal)).find((m) => m.id === id) ?? null;

export const searchAllMachines = async (q: string, signal: AbortSignal): Promise<MachineDto[]> =>
  (await machineService.list({ page: 1, page_size: LOOKUP_PAGE_SIZE, q }, signal)).items;

/**
 * Machine id → `asset code · name` for field lists: the register (first 200) for those who read it,
 * else the machines the caller works on. Unknown ids fall back to a short id.
 */
export function useFieldMachineLabels(): (id: string) => string {
  const { hasPermission } = useSession();
  const register = hasPermission(PERMISSIONS.tenantMachineRead);
  const load = useCallback(
    async (signal: AbortSignal): Promise<MachineDto[]> =>
      register
        ? (await machineService.list({ page: 1, page_size: 200 }, signal)).items
        : machineService.fieldMachines(undefined, signal),
    [register],
  );
  const res = useAsyncResource(load);
  return useMemo(() => {
    const names = new Map((res.data ?? []).map((m) => [m.id, machineLabel(m)]));
    return (id: string) => names.get(id) ?? `${id.slice(0, 8)}…`;
  }, [res.data]);
}
