import { PERMISSIONS } from '../../../access/permissionCodes';
import type { PermissionRequirement } from '../../../session/permissions';

/** Holding any of these means office oversight: such users keep the Dashboard. */
export const OFFICE_PERMISSIONS = [
  PERMISSIONS.tenantMachineReportApprove,
  PERMISSIONS.tenantFinanceRead,
] as const;

/**
 * A field user: may submit machine reports but has no office oversight. Their console opens on the
 * machine report page, and their pickers use the field-scoped lists (machines they work on).
 */
export function isFieldUser(
  hasPermission: (p: PermissionRequirement, match?: 'all' | 'any') => boolean,
): boolean {
  return (
    hasPermission(PERMISSIONS.tenantMachineReportSubmit) &&
    !hasPermission(OFFICE_PERMISSIONS, 'any')
  );
}
