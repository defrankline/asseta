import { Box, Button, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { notificationChannelService } from '../../api/services/notificationChannelService';
import type { PushDeviceDto } from '../../api/types';
import { StaticTable } from '../../components/data/StaticTable';
import type { DataColumn } from '../../components/data/ServerDataTable';
import { StatusChip } from '../../components/display/StatusChip';
import { AsyncContent } from '../../components/feedback/AsyncContent';
import { ConfirmDialog } from '../../components/forms/ConfirmDialog';
import { ShowInactiveToggle } from '../../components/lifecycle/ShowInactiveToggle';
import { useAsyncResource } from '../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../hooks/useDisplayTimeZone';
import { useIdempotencyKey } from '../../hooks/useIdempotencyKey';
import { useNotify } from '../../notifications/useNotify';
import { formatInstantIn } from '../../utils/time';

const PLATFORM_LABELS: Readonly<Record<string, string>> = { ANDROID: 'Android', IOS: 'iOS' };
const APP_LABELS: Readonly<Record<string, string>> = {
  OWNER: 'Owner app',
  SUPERVISOR: 'Supervisor app',
};
const REASON_LABELS: Readonly<Record<string, string>> = {
  USER: 'Removed by you',
  PROVIDER_UNREGISTERED: 'App uninstalled or signed out',
};

function deviceLabel(d: PushDeviceDto): string {
  const name = d.device_label ?? PLATFORM_LABELS[d.platform] ?? d.platform;
  return `${name} · ${APP_LABELS[d.app] ?? d.app}`;
}

function DeactivateDeviceDialog({
  device,
  onClose,
  onDone,
}: {
  device: PushDeviceDto;
  onClose: () => void;
  onDone: () => void;
}) {
  const notify = useNotify();
  const keyFor = useIdempotencyKey();
  return (
    <ConfirmDialog
      open
      destructive
      title={`Stop notifications to ${deviceLabel(device)}`}
      message="This device stops receiving push notifications. It is kept in the list as inactive; signing in to the app again registers it anew."
      confirmLabel="Deactivate device"
      onClose={onClose}
      onConfirm={async () => {
        await notificationChannelService.deactivateDevice(device.id, keyFor({ id: device.id }));
        notify.success(`${deviceLabel(device)} will no longer receive push notifications.`);
        onDone();
      }}
    />
  );
}

/** The signed-in user's registered phones (`/me/push-devices`), with deactivation. */
export function PushDevicesSection() {
  const tz = useDisplayTimeZone();
  const [showInactive, setShowInactive] = useState(false);
  const [removing, setRemoving] = useState<PushDeviceDto | null>(null);
  const load = useCallback(
    (signal: AbortSignal) => notificationChannelService.listDevices(showInactive, signal),
    [showInactive],
  );
  const devices = useAsyncResource(load);
  const columns: DataColumn<PushDeviceDto>[] = [
    {
      id: 'device',
      header: 'Device',
      render: (d) => (
        <>
          <span>{deviceLabel(d)}</span>
          <Typography variant="caption" color="text.secondary" component="div">
            Token ending {d.token_hint}
            {d.app_version !== null ? ` · version ${d.app_version}` : ''}
          </Typography>
        </>
      ),
    },
    {
      id: 'scope',
      header: 'Receives',
      render: (d) => (d.tenant_id === null ? 'All your consoles' : 'One tenant only'),
    },
    {
      id: 'registered',
      header: 'Last registered',
      render: (d) => formatInstantIn(d.last_registered_at, tz),
    },
    {
      id: 'status',
      header: 'Status',
      render: (d) =>
        d.active ? (
          <StatusChip status="ACTIVE" tones={{ ACTIVE: 'success' }} label="Active" />
        ) : (
          <>
            <StatusChip status="INACTIVE" label="Inactive" />
            {d.deactivation_reason !== null && (
              <Typography variant="caption" color="text.secondary" component="div">
                {REASON_LABELS[d.deactivation_reason] ?? d.deactivation_reason}
              </Typography>
            )}
          </>
        ),
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (d) =>
        d.active ? (
          <Button
            size="small"
            color="error"
            aria-label={`Deactivate ${deviceLabel(d)}`}
            onClick={() => {
              setRemoving(d);
            }}
          >
            Deactivate
          </Button>
        ) : null,
    },
  ];
  return (
    <Box component="section" aria-labelledby="devices-heading" className="flex flex-col gap-3">
      <Box className="flex flex-wrap items-end justify-between gap-2">
        <Box>
          <Typography id="devices-heading" variant="h6" component="h2">
            My devices
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Phones signed in to the Asseta apps that receive your push notifications.
          </Typography>
        </Box>
        <ShowInactiveToggle
          checked={showInactive}
          onChange={setShowInactive}
          label="Show inactive"
        />
      </Box>
      <AsyncContent
        resource={devices}
        isEmpty={(p) => p.items.length === 0}
        emptyTitle="No registered devices"
        emptyDescription="Sign in to the owner or supervisor app on your phone to receive push notifications."
        errorTitle="Could not load your devices"
      >
        {(p) => (
          <StaticTable
            columns={columns}
            rows={p.items}
            getRowId={(d) => d.id}
            ariaLabel="My devices"
            isRowMuted={(d) => !d.active}
          />
        )}
      </AsyncContent>
      {removing !== null && (
        <DeactivateDeviceDialog
          device={removing}
          onClose={() => {
            setRemoving(null);
          }}
          onDone={() => {
            setRemoving(null);
            devices.reload();
          }}
        />
      )}
    </Box>
  );
}
