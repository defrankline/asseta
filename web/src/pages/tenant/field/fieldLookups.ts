import { useCallback, useMemo } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { jobService } from '../../../api/services/jobService';
import { machineService } from '../../../api/services/machineService';
import type { JobDto, MachineDto } from '../../../api/types';
import { LOOKUP_PAGE_SIZE } from '../../../components/data/AsyncAutocomplete';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useSession } from '../../../session/useSession';
import { machineLabel } from '../shared/display';

/**
 * Field-scoped lookups. A supervisor sees only the jobs they supervise (`mine`) and the machines they
 * work on (`/tenant/field/machines`, no machine register access); office roles search everything.
 * Every search passes the typed text to the API; nothing is filtered in the browser.
 */

/** Users who manage jobs (write / approve) work on any job; everyone else on their own. */
export function useSeesAllJobs(): boolean {
  const { hasPermission } = useSession();
  return hasPermission([PERMISSIONS.tenantJobWrite, PERMISSIONS.tenantJobApprove], 'any');
}

export const searchMyJobs = async (q: string, signal: AbortSignal): Promise<JobDto[]> =>
  (
    await jobService.list(
      { page: 1, page_size: LOOKUP_PAGE_SIZE, q, filters: { mine: 'true' } },
      signal,
    )
  ).items;

export const searchAllJobs = async (q: string, signal: AbortSignal): Promise<JobDto[]> =>
  (await jobService.list({ page: 1, page_size: LOOKUP_PAGE_SIZE, q }, signal)).items;

export const searchFieldMachines = (q: string, signal: AbortSignal): Promise<MachineDto[]> =>
  jobService.fieldMachines(q.trim() === '' ? undefined : q, signal);

export const resolveFieldMachine = async (
  id: string,
  signal: AbortSignal,
): Promise<MachineDto | null> =>
  (await jobService.fieldMachines(undefined, signal)).find((m) => m.id === id) ?? null;

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
        : jobService.fieldMachines(undefined, signal),
    [register],
  );
  const res = useAsyncResource(load);
  return useMemo(() => {
    const names = new Map((res.data ?? []).map((m) => [m.id, machineLabel(m)]));
    return (id: string) => names.get(id) ?? `${id.slice(0, 8)}…`;
  }, [res.data]);
}

/** Job id → job number for field lists (the caller's jobs, or every job for job managers; first 200). */
export function useFieldJobLabels(): (id: string) => string {
  const all = useSeesAllJobs();
  const load = useCallback(
    async (signal: AbortSignal): Promise<JobDto[]> =>
      (
        await jobService.list(
          { page: 1, page_size: 200, filters: { mine: all ? undefined : 'true' } },
          signal,
        )
      ).items,
    [all],
  );
  const res = useAsyncResource(load);
  return useMemo(() => {
    const names = new Map((res.data ?? []).map((j) => [j.id, j.job_number]));
    return (id: string) => names.get(id) ?? `${id.slice(0, 8)}…`;
  }, [res.data]);
}
