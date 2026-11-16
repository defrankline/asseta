import { useCallback } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { machineService } from '../../../api/services/machineService';
import type { MachineDto } from '../../../api/types';
import { LOOKUP_PAGE_SIZE } from '../../../components/data/AsyncAutocomplete';
import { useSession } from '../../../session/useSession';

/**
 * Machine search for pickers: the machine register for those who may read it, else the machines the caller works
 * on (`/tenant/field/machines`: assigned to them). Supervisors have no register access,
 * so a register search would be refused (403).
 */
export function useMachineSearch(): (q: string, signal: AbortSignal) => Promise<MachineDto[]> {
  const { hasPermission } = useSession();
  const register = hasPermission(PERMISSIONS.tenantMachineRead);
  return useCallback(
    async (q: string, signal: AbortSignal) =>
      register
        ? (await machineService.list({ page: 1, page_size: LOOKUP_PAGE_SIZE, q }, signal)).items
        : machineService.fieldMachines(q.trim() === '' ? undefined : q, signal),
    [register],
  );
}
