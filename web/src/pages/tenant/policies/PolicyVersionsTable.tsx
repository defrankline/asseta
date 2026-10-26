import { useCallback } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { machineService } from '../../../api/services/machineService';
import { staffService } from '../../../api/services/staffService';
import type { PolicyVersionDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { StatusChip } from '../../../components/display/StatusChip';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { findField, formatPolicyValue } from './policyFields';

interface PolicyVersionsTableProps {
  versions: readonly PolicyVersionDto[];
  timeZone: string;
  /** Resolves a machine/site id to a label. */
  refLabel: (id: string) => string;
}

function summary(v: PolicyVersionDto): string {
  return Object.entries(v.values)
    .map(([k, value]) => {
      const def = findField(v.policy_type, k);
      return `${def?.label ?? k}: ${formatPolicyValue(def, value)}`;
    })
    .join(' · ');
}

const SCOPE_TONES = {
  PLATFORM: 'default',
  TENANT: 'info',
  MACHINE: 'success',
  SITE: 'warning',
  STAFF: 'default',
  MACHINE_CATEGORY: 'success',
} as const;

/** A staff-scoped version names the person (resolved by id; the id when it cannot be read). */
function StaffRef({ staffId }: { staffId: string }) {
  const canRead = useSession().hasPermission(PERMISSIONS.tenantStaffRead);
  const load = useCallback((signal: AbortSignal) => staffService.get(staffId, signal), [staffId]);
  const res = useAsyncResource(load, [staffId], canRead);
  return <>{res.data?.full_name ?? staffId}</>;
}

/** A category-scoped version names the category (resolved by id; the id when it cannot be read). */
function CategoryRef({ categoryId }: { categoryId: string }) {
  const load = useCallback(
    (signal: AbortSignal) => machineService.getCategory(categoryId, signal),
    [categoryId],
  );
  const res = useAsyncResource(load, [categoryId]);
  return <>{res.data?.name ?? categoryId}</>;
}

/** Version history (newest first); versions are immutable and effective-dated. */
export function PolicyVersionsTable({ versions, timeZone, refLabel }: PolicyVersionsTableProps) {
  const rows = [...versions].sort((a, b) => b.created_at.localeCompare(a.created_at));
  const columns: DataColumn<PolicyVersionDto>[] = [
    { id: 'version', header: 'Version', render: (v) => `v${String(v.version)}` },
    {
      id: 'scope',
      header: 'Scope',
      render: (v) => <StatusChip status={v.scope} tones={SCOPE_TONES} />,
    },
    {
      id: 'ref',
      header: 'Applies to',
      render: (v) =>
        v.scope_ref_id === null ? (
          'All'
        ) : v.scope === 'STAFF' ? (
          <StaffRef staffId={v.scope_ref_id} />
        ) : v.scope === 'MACHINE_CATEGORY' ? (
          <CategoryRef categoryId={v.scope_ref_id} />
        ) : (
          refLabel(v.scope_ref_id)
        ),
    },
    {
      id: 'effective',
      header: 'Effective from',
      render: (v) => formatInstantIn(v.effective_from, timeZone),
    },
    { id: 'values', header: 'Values', render: (v) => summary(v) },
    { id: 'reason', header: 'Reason', render: (v) => v.reason },
    { id: 'created', header: 'Created', render: (v) => formatInstantIn(v.created_at, timeZone) },
  ];
  return (
    <StaticTable ariaLabel="Policy versions" columns={columns} rows={rows} getRowId={(v) => v.id} />
  );
}
