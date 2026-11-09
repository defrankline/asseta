import { FormControlLabel, Link, Paper, Switch } from '@mui/material';
import { useCallback } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router';
import type { PendingItemDto } from '../../../api/custodyTypes';
import { accountabilityService } from '../../../api/services/accountabilityService';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { MoneyText } from '../../../components/display/MoneyText';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import { hoursText } from '../hours/hoursDisplay';
import { machineText, nameOr } from '../shared/names';
import { PersonName } from '../shared/PersonName';

function PendingAmount({ item: p }: { item: PendingItemDto }) {
  if (p.amount === null) return <>—</>;
  if (p.unit === 'HOURS') return <>{hoursText(p.amount)}</>;
  return p.currency === null ? (
    <>{p.amount}</>
  ) : (
    <MoneyText amount={p.amount} currency={p.currency} />
  );
}

function forWhom(p: PendingItemDto): string {
  if (p.customer_id !== null) return nameOr(p.customer_name, p.customer_id);
  if (p.staff_member_id !== null) return nameOr(p.staff_member_name, p.staff_member_id);
  if (p.machine_id !== null) return machineText(p.machine_code, p.machine_name, p.machine_id);
  return '—';
}

/** Everything proposed and not yet decided across all flows, oldest first (guideline section 8). */
export function PendingAdjustmentsPage() {
  const timeZone = useDisplayTimeZone();
  const [params, setParams] = useSearchParams();
  const allApprovals = params.get('all_approvals') === 'true';
  const fetchPage = useCallback<FetchPage<PendingItemDto>>(
    (query, signal) => accountabilityService.pendingAdjustments(query, signal),
    [],
  );
  const columns: DataColumn<PendingItemDto>[] = [
    {
      id: 'ref',
      header: 'Record',
      render: (p) => {
        const label = p.reference ?? humanize(p.record_type);
        return p.route === null ? (
          label
        ) : (
          <Link component={RouterLink} to={p.route}>
            {label}
          </Link>
        );
      },
    },
    { id: 'kind', header: 'What', render: (p) => humanize(p.kind) },
    { id: 'for', header: 'For', render: forWhom },
    { id: 'status', header: 'Status', render: (p) => humanize(p.status) },
    {
      id: 'by',
      header: 'Requested by',
      render: (p) => <PersonName userId={p.requested_by} name={p.requested_by_name} />,
    },
    { id: 'at', header: 'Requested', render: (p) => formatInstantIn(p.requested_at, timeZone) },
    { id: 'amount', header: 'Amount', align: 'right', render: (p) => <PendingAmount item={p} /> },
  ];
  return (
    <>
      <PageHeader
        title="Pending adjustments"
        subtitle="Everything proposed and not yet decided, across every flow, oldest first"
      />
      <Paper variant="outlined" className="p-3">
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(p) => `${p.record_type}-${p.id}`}
          searchPlaceholder="Search number or reference"
          filters={{ all_approvals: allApprovals ? 'true' : undefined }}
          emptyTitle="Nothing is waiting for a decision"
          toolbar={
            <FormControlLabel
              label="Every outstanding approval"
              control={
                <Switch
                  checked={allApprovals}
                  onChange={(e) => {
                    setParams(e.target.checked ? { all_approvals: 'true' } : {}, { replace: true });
                  }}
                />
              }
            />
          }
        />
      </Paper>
    </>
  );
}
