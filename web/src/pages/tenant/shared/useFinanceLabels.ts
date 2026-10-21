import { useCallback, useMemo } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { customerService } from '../../../api/services/customerService';
import { expenseCategoryService } from '../../../api/services/expenseCategoryService';
import { staffService } from '../../../api/services/staffService';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useSession } from '../../../session/useSession';
import { shortId } from './financeDisplay';

type Labeler = (id: string | null) => string;

function useLabelMap<T extends { id: string }>(
  load: (signal: AbortSignal) => Promise<readonly T[]>,
  enabled: boolean,
  labelOf: (row: T) => string,
): Labeler {
  const res = useAsyncResource(load, [], enabled);
  return useMemo(() => {
    const names = new Map((res.data ?? []).map((r) => [r.id, labelOf(r)]));
    return (id: string | null) => (id === null ? '—' : (names.get(id) ?? shortId(id)));
    // labelOf is a module-level formatter at every call site.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [res.data]);
}

/** Customer id → `code · name` for list displays (first 200 customers, inactive included). */
export function useCustomerLabels(): Labeler {
  const { hasPermission } = useSession();
  const load = useCallback(
    async (signal: AbortSignal) =>
      (
        await customerService.list(
          { page: 1, page_size: 200, filters: { include_inactive: 'true' } },
          signal,
        )
      ).items,
    [],
  );
  return useLabelMap(load, hasPermission(PERMISSIONS.tenantCustomerRead), (c) => c.name);
}

/** Staff id → full name for list displays (first 200 staff, inactive included). */
export function useStaffLabels(): Labeler {
  const { hasPermission } = useSession();
  const load = useCallback(
    async (signal: AbortSignal) =>
      (
        await staffService.list(
          { page: 1, page_size: 200, filters: { include_inactive: 'true' } },
          signal,
        )
      ).items,
    [],
  );
  return useLabelMap(load, hasPermission(PERMISSIONS.tenantStaffRead), (s) => s.full_name);
}

/** Expense category id → `code · name` (inactive included, so past expenses keep their label). */
export function useExpenseCategoryLabels(): Labeler {
  const { hasPermission } = useSession();
  const load = useCallback(
    (signal: AbortSignal) => expenseCategoryService.list(signal, undefined, true),
    [],
  );
  return useLabelMap(
    load,
    hasPermission(PERMISSIONS.tenantExpenseRead),
    (c) => `${c.code} · ${c.name}`,
  );
}

/** The signed-in user's id (for segregation-of-duties checks against `recorded_by`). */
export function useMyUserId(): string | null {
  return useSession().me?.user_id ?? null;
}
