import Add from '@mui/icons-material/Add';
import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { gatewayService } from '../../../api/services/platformCatalogService';
import type { GatewayCreatedDto, GatewayDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import { DetailsDrawer } from '../../../components/lifecycle/DetailsDrawer';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { standardRowActions, type RowAction } from '../../../components/lifecycle/rowActions';
import { ShowInactiveToggle } from '../../../components/lifecycle/ShowInactiveToggle';
import { useLifecycleDialog } from '../../../components/lifecycle/useLifecycleDialog';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstant } from '../../../utils/dates';
import { CreateGatewayDialog, GatewayKeyDialog } from './GatewayDialogs';

const DEACTIVATE_CONSEQUENCES =
  'Its key stops being accepted immediately: telemetry pushed by this gateway is rejected until it is reactivated.';

/** Telemetry gateways (keys are never listed). */
export function GatewaysTab() {
  const notify = useNotify();
  const { hasPermission } = useSession();
  const canManage = hasPermission(PERMISSIONS.platformGatewayManage);
  const [showInactive, setShowInactive] = useState(false);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<GatewayCreatedDto | null>(null);
  const [viewingId, setViewingId] = useState<string | null>(null);
  const load = useCallback(
    (signal: AbortSignal) => gatewayService.list(signal, showInactive),
    [showInactive],
  );
  const gateways = useAsyncResource(load);
  const lifecycle = useLifecycleDialog<GatewayDto>({
    labelOf: (g) => g.name,
    noun: 'gateway',
    consequences: DEACTIVATE_CONSEQUENCES,
    deactivate: (g, body, key) => gatewayService.deactivate(g.id, body, key),
    reactivate: (g, body, key) => gatewayService.reactivate(g.id, body, key),
    onDone: (g, kind) => {
      notify.success(`Gateway ${g.name} ${kind === 'deactivate' ? 'deactivated' : 'reactivated'}.`);
      gateways.reload();
    },
    onReload: gateways.reload,
  });

  const actionsFor = (g: GatewayDto, inDrawer: boolean): RowAction[] =>
    standardRowActions({
      active: g.active,
      canChangeState: canManage,
      ...(inDrawer
        ? {}
        : {
            onView: () => {
              setViewingId(g.id);
            },
          }),
      onDeactivate: () => {
        lifecycle.open('deactivate', g);
      },
      onReactivate: () => {
        lifecycle.open('reactivate', g);
      },
    });

  const columns: DataColumn<GatewayDto>[] = [
    { id: 'name', header: 'Name', render: (g) => <strong>{g.name}</strong> },
    { id: 'adapter', header: 'Adapter', render: (g) => g.adapter },
    {
      id: 'seen',
      header: 'Last seen',
      render: (g) => (g.last_seen_at === null ? 'Never' : formatInstant(g.last_seen_at)),
    },
    { id: 'created', header: 'Created', render: (g) => formatInstant(g.created_at) },
    { id: 'state', header: 'State', render: (g) => <ActiveChip active={g.active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (g) => <RowActionsMenu label={`gateway ${g.name}`} actions={actionsFor(g, false)} />,
    },
  ];
  const viewed = gateways.data?.find((g) => g.id === viewingId) ?? null;

  return (
    <Box className="flex flex-col gap-3">
      <Box className="flex flex-wrap items-center gap-3">
        <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} />
        <Box className="flex-1" />
        {canManage && (
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => {
              setCreating(true);
            }}
          >
            Add gateway
          </Button>
        )}
      </Box>
      <AsyncContent
        resource={gateways}
        isEmpty={(rows) => rows.length === 0}
        emptyTitle="No telemetry gateways"
        errorTitle="Could not load telemetry gateways"
      >
        {(rows) => (
          <StaticTable
            ariaLabel="Telemetry gateways"
            columns={columns}
            rows={rows}
            getRowId={(g) => g.id}
            isRowMuted={(g) => !g.active}
            onRowClick={(g) => {
              setViewingId(g.id);
            }}
          />
        )}
      </AsyncContent>
      {viewed !== null && (
        <DetailsDrawer
          title={`Gateway ${viewed.name}`}
          status={<ActiveChip active={viewed.active} />}
          actions={<ActionButtons actions={actionsFor(viewed, true)} />}
          onClose={() => {
            setViewingId(null);
          }}
        >
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Name', value: viewed.name },
              { label: 'Adapter', value: viewed.adapter },
              {
                label: 'Last seen',
                value: viewed.last_seen_at === null ? 'Never' : formatInstant(viewed.last_seen_at),
              },
              { label: 'Created', value: formatInstant(viewed.created_at) },
              { label: 'Key', value: 'Shown only once at creation' },
            ]}
          />
        </DetailsDrawer>
      )}
      {creating && (
        <CreateGatewayDialog
          onClose={() => {
            setCreating(false);
          }}
          onCreated={(c) => {
            setCreated(c);
            gateways.reload();
          }}
        />
      )}
      {created !== null && (
        <GatewayKeyDialog
          created={created}
          onClose={() => {
            setCreated(null);
          }}
        />
      )}
      {lifecycle.dialog}
    </Box>
  );
}
