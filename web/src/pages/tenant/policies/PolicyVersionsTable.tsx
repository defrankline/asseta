import type { PolicyVersionDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { StatusChip } from '../../../components/display/StatusChip';
import { formatInstantIn } from '../../../utils/time';
import { formatPolicyValue, TRACKING_FIELDS } from './policyFields';

interface PolicyVersionsTableProps {
  versions: readonly PolicyVersionDto[];
  timeZone: string;
  /** Resolves a machine/site id to a label. */
  refLabel: (id: string) => string;
}

function summary(values: Record<string, unknown>): string {
  return Object.entries(values)
    .map(([k, v]) => {
      const def = TRACKING_FIELDS.find((f) => f.key === k);
      return `${def?.label ?? k}: ${formatPolicyValue(def, v)}`;
    })
    .join(' · ');
}

const SCOPE_TONES = {
  PLATFORM: 'default',
  TENANT: 'info',
  MACHINE: 'success',
  SITE: 'warning',
} as const;

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
      render: (v) => (v.scope_ref_id === null ? 'All' : refLabel(v.scope_ref_id)),
    },
    {
      id: 'effective',
      header: 'Effective from',
      render: (v) => formatInstantIn(v.effective_from, timeZone),
    },
    { id: 'values', header: 'Values', render: (v) => summary(v.values) },
    { id: 'reason', header: 'Reason', render: (v) => v.reason },
    { id: 'created', header: 'Created', render: (v) => formatInstantIn(v.created_at, timeZone) },
  ];
  return (
    <StaticTable ariaLabel="Policy versions" columns={columns} rows={rows} getRowId={(v) => v.id} />
  );
}
