import { Button, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { deviceService, type TenantDeviceDto } from '../../../api/services/deviceService';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { StatusChip, type StatusTone } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { LifecycleActionDialog } from '../../../components/lifecycle/LifecycleActionDialog';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';

const TONES: Readonly<Record<string, StatusTone>> = { ACTIVE: 'success', REVOKED: 'error' };
const PLATFORMS: Readonly<Record<string, string>> = { ANDROID: 'Android', IOS: 'iOS' };

const person = (d: TenantDeviceDto) => d.user_name ?? 'Unknown person';
const phone = (d: TenantDeviceDto) => d.device_model ?? 'Model not known';

/** Device sessions exist only for the app that works offline, the Supervisor app. */
function appLabel(d: TenantDeviceDto): string {
  return `Supervisor app · ${PLATFORMS[d.platform] ?? d.platform} · version ${d.app_version}`;
}

function RevokeDialog({
  device,
  onClose,
  onDone,
}: {
  device: TenantDeviceDto;
  onClose: () => void;
  onDone: () => void;
}) {
  const notify = useNotify();
  return (
    <LifecycleActionDialog<TenantDeviceDto>
      title={`Revoke ${person(device)}'s phone`}
      description={
        <>
          <p className="m-0">
            <strong>Any unsent work on this phone will be erased</strong> the next time it connects,
            and it cannot be recovered. Records that have already synced are not affected.
          </p>
          <p className="mb-0 mt-2">
            The phone can no longer sync or be registered again. {person(device)} will need another
            phone.
          </p>
        </>
      }
      confirmLabel="Revoke phone"
      reasonLabel="Reason for revoking"
      errorHints={{ DEVICE_ALREADY_REVOKED: 'This phone was already revoked. Reload the list.' }}
      onConfirm={(reason, key) => deviceService.revoke(device.id, reason, key)}
      onDone={() => {
        notify.success(`${person(device)}'s phone was revoked.`);
        onDone();
      }}
      onClose={onClose}
    />
  );
}

/** The company's registered phones: who holds each one, when it last synced, and revoking a lost one. */
export function DevicesPage() {
  const timeZone = useDisplayTimeZone();
  const [reloadKey, setReloadKey] = useState(0);
  const [revoking, setRevoking] = useState<TenantDeviceDto | null>(null);
  const fetchPage = useCallback<FetchPage<TenantDeviceDto>>(
    (query, signal) => deviceService.list(query, signal),
    [],
  );

  const columns: DataColumn<TenantDeviceDto>[] = [
    { id: 'person', header: 'Person', render: person },
    { id: 'app', header: 'App', render: appLabel },
    {
      id: 'model',
      header: 'Phone',
      render: (d) => (
        <>
          <span>{phone(d)}</span>
          <Typography variant="caption" color="text.secondary" component="div">
            {d.device_id}
          </Typography>
        </>
      ),
    },
    {
      id: 'seen',
      header: 'Last seen',
      render: (d) => (d.last_sync_at ? formatInstantIn(d.last_sync_at, timeZone) : 'Never synced'),
    },
    {
      id: 'status',
      header: 'Status',
      render: (d) => (
        <>
          <StatusChip status={d.status} tones={TONES} />
          {d.revoked_at !== null && (
            <Typography variant="caption" color="text.secondary" component="div">
              {formatInstantIn(d.revoked_at, timeZone)}
              {d.revoked_by_name !== null ? ` by ${d.revoked_by_name}` : ''}
              {d.revoke_reason !== null ? `: ${d.revoke_reason}` : ''}
            </Typography>
          )}
        </>
      ),
    },
    {
      id: 'actions',
      header: '',
      render: (d) =>
        d.status === 'ACTIVE' ? (
          <CanMutate permission={PERMISSIONS.tenantDeviceManage}>
            <Button
              size="small"
              color="error"
              onClick={() => {
                setRevoking(d);
              }}
            >
              Revoke
            </Button>
          </CanMutate>
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader
        title="Devices"
        subtitle="Phones signed in to the Supervisor app, and revoking a lost one"
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(d) => d.id}
        reloadKey={reloadKey}
        searchPlaceholder="Search person, phone or version"
        emptyTitle="No phones registered"
        emptyDescription="A phone appears here after someone signs in to the Supervisor app on it."
      />
      {revoking !== null && (
        <RevokeDialog
          device={revoking}
          onClose={() => {
            setRevoking(null);
          }}
          onDone={() => {
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
