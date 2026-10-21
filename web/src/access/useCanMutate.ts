import type { PermissionRequirement } from '../session/permissions';
import { useSession } from '../session/useSession';

/** Hook form of `<CanMutate>`: permitted and the active tenant is not READ_ONLY. */
export function useCanMutate(permission: PermissionRequirement): boolean {
  const { status, hasPermission, isReadOnly } = useSession();
  return status === 'ready' && !isReadOnly && hasPermission(permission);
}

/** Predicate form for checking several mutating permissions (e.g. one per action button). */
export function useMutationGuard(): (permission: PermissionRequirement) => boolean {
  const { status, hasPermission, isReadOnly } = useSession();
  return (permission) => status === 'ready' && !isReadOnly && hasPermission(permission);
}
