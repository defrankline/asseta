import Add from '@mui/icons-material/Add';
import { Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { tenantService } from '../../../api/services/tenantService';
import type { OnboardResultDto, TenantDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { tenantDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstant } from '../../../utils/dates';
import { ACCESS_TONES, TENANT_STATUS_TONES, VERIFICATION_TONES } from '../shared/billingDisplay';
import { OnboardTenantDialog } from './OnboardTenantDialog';
import { TemporaryPasswordDialog } from './TemporaryPasswordDialog';

const columns: DataColumn<TenantDto>[] = [
  {
    id: 'name',
    header: 'Tenant',
    sortField: 'name',
    render: (t) => (
      <span>
        <strong>{t.display_name}</strong>
        <br />
        <small>{t.legal_name}</small>
      </span>
    ),
  },
  { id: 'contact', header: 'Contact', render: (t) => `${t.contact_name} · ${t.contact_email}` },
  {
    id: 'status',
    header: 'Status',
    render: (t) => <StatusChip status={t.status} tones={TENANT_STATUS_TONES} />,
  },
  {
    id: 'verification',
    header: 'Verification',
    render: (t) => <StatusChip status={t.verification_status} tones={VERIFICATION_TONES} />,
  },
  {
    id: 'access',
    header: 'Access',
    render: (t) => <StatusChip status={t.access_state} tones={ACCESS_TONES} />,
  },
  {
    id: 'created_at',
    header: 'Created',
    sortField: 'created_at',
    render: (t) => formatInstant(t.created_at),
  },
];

export function TenantsPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const [onboarding, setOnboarding] = useState(false);
  const [result, setResult] = useState<OnboardResultDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      tenantService.list(
        {
          page: q.page,
          page_size: q.page_size,
          ...(q.sort !== undefined ? { sort: q.sort } : {}),
          ...(q.q !== undefined ? { q: q.q } : {}),
        },
        signal,
      ),
    [],
  );

  return (
    <>
      <PageHeader
        title="Tenants"
        subtitle="Companies subscribed to Asseta"
        actions={
          <Can permission={PERMISSIONS.platformTenantCreate}>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setOnboarding(true);
              }}
            >
              Onboard tenant
            </Button>
          </Can>
        }
      />
      <ServerDataTable<TenantDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(t) => t.id}
        initialSort="-created_at"
        searchPlaceholder="Search tenants"
        emptyTitle="No tenants yet"
        reloadKey={reloadKey}
        onRowClick={(t) => {
          void navigate(tenantDetailPath(t.id));
        }}
      />
      {onboarding && (
        <OnboardTenantDialog
          onClose={() => {
            setOnboarding(false);
          }}
          onOnboarded={(r) => {
            setResult(r);
            setReloadKey((k) => k + 1);
            notify.success(`Tenant ${r.tenant.display_name} onboarded.`);
          }}
        />
      )}
      {result !== null && (
        <TemporaryPasswordDialog
          result={result}
          onClose={() => {
            setResult(null);
          }}
        />
      )}
    </>
  );
}
