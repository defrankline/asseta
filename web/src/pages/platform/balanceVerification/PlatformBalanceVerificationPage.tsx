import { Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { newUuid } from '../../../api/ids';
import {
  dataProtectionService,
  type TenantVerificationDto,
} from '../../../api/services/dataProtectionService';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { StatusChip, type StatusTone } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstant } from '../../../utils/dates';

const TONES: Readonly<Record<string, StatusTone>> = { MATCHED: 'success', MISMATCHES: 'error' };

/** Latest balance verification of every tenant. Counts only: findings stay with the tenant. */
export function PlatformBalanceVerificationPage() {
  const notify = useNotify();
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<TenantVerificationDto>>(
    (query, signal) => dataProtectionService.platformOverview(query, signal),
    [],
  );
  const run = (line: TenantVerificationDto) => {
    dataProtectionService
      .platformRun(line.tenant_id, newUuid())
      .then((r) => {
        notify.success(`${line.tenant_name}: ${String(r.mismatch_count)} difference(s).`);
        setReloadKey((k) => k + 1);
      })
      .catch(() => {
        notify.error('The verification could not be run.');
      });
  };
  const columns: DataColumn<TenantVerificationDto>[] = [
    { id: 'tenant', header: 'Tenant', render: (l) => l.tenant_name },
    {
      id: 'live',
      header: 'Live since',
      render: (l) => (l.live_at ? formatInstant(l.live_at) : '—'),
    },
    {
      id: 'at',
      header: 'Last run',
      render: (l) => (l.latest ? formatInstant(l.latest.started_at) : '—'),
    },
    {
      id: 'outcome',
      header: 'Result',
      render: (l) => (l.latest ? <StatusChip status={l.latest.outcome} tones={TONES} /> : '—'),
    },
    {
      id: 'checked',
      header: 'Checked',
      align: 'right',
      render: (l) => l.latest?.checked_count ?? '—',
    },
    {
      id: 'diffs',
      header: 'Differences',
      align: 'right',
      render: (l) => l.latest?.mismatch_count ?? '—',
    },
    {
      id: 'actions',
      header: '',
      render: (l) => (
        <Can permission={PERMISSIONS.platformBalanceVerify}>
          <Button
            size="small"
            onClick={() => {
              run(l);
            }}
          >
            Verify now
          </Button>
        </Can>
      ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Balance verification"
        subtitle="Latest verification of every tenant's balances against its records (counts only)"
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(l) => l.tenant_id}
        reloadKey={reloadKey}
        searchable
        searchPlaceholder="Search tenants"
        emptyTitle="No tenants"
      />
    </>
  );
}
