import Add from '@mui/icons-material/Add';
import SearchIcon from '@mui/icons-material/Search';
import { Box, Button, InputAdornment, TextField } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { trackerModelService } from '../../../api/services/platformCatalogService';
import type { TrackerModelDto } from '../../../api/types';
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
import { useDebouncedValue } from '../../../hooks/useDebouncedValue';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstant } from '../../../utils/dates';
import { CAPABILITY_LABELS } from '../../tenant/shared/display';
import { TrackerModelDialog } from './TrackerModelDialog';
import { MODEL_ERROR_HINTS, trackerModelLabel } from './trackerModelForm';

type Editing = { kind: 'new' } | { kind: 'edit'; model: TrackerModelDto } | null;

const WITHDRAW_CONSEQUENCES =
  'Tenants can no longer register new trackers with this model. Trackers already registered keep working.';

/** Approved tracker driver/model catalog with withdraw / restore. */
export function TrackerModelsTab() {
  const notify = useNotify();
  const { hasPermission } = useSession();
  const canManage = hasPermission(PERMISSIONS.platformTrackerModelManage);
  const [search, setSearch] = useState('');
  const q = useDebouncedValue(search.trim(), 300);
  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<Editing>(null);
  const [viewingId, setViewingId] = useState<string | null>(null);

  const load = useCallback(
    (signal: AbortSignal) => trackerModelService.list(signal, q, showInactive),
    [q, showInactive],
  );
  const models = useAsyncResource(load);
  const lifecycle = useLifecycleDialog<TrackerModelDto>({
    labelOf: trackerModelLabel,
    noun: 'tracker model',
    deactivateLabel: 'Withdraw',
    reactivateLabel: 'Restore',
    consequences: WITHDRAW_CONSEQUENCES,
    errorHints: MODEL_ERROR_HINTS,
    deactivate: (m, body, key) =>
      trackerModelService.deactivate(m.id, { ...body, version: m.version }, key),
    reactivate: (m, body, key) =>
      trackerModelService.reactivate(m.id, { ...body, version: m.version }, key),
    onDone: (m, kind) => {
      notify.success(
        `${trackerModelLabel(m)} ${kind === 'deactivate' ? 'withdrawn' : 'restored'}.`,
      );
      models.reload();
    },
    onReload: models.reload,
  });

  const actionsFor = (m: TrackerModelDto, inDrawer: boolean): RowAction[] =>
    standardRowActions({
      active: m.approved,
      canEdit: canManage,
      canChangeState: canManage,
      deactivateLabel: 'Withdraw',
      reactivateLabel: 'Restore',
      ...(inDrawer
        ? {}
        : {
            onView: () => {
              setViewingId(m.id);
            },
          }),
      onEdit: () => {
        setViewingId(null);
        setEditing({ kind: 'edit', model: m });
      },
      onDeactivate: () => {
        lifecycle.open('deactivate', m);
      },
      onReactivate: () => {
        lifecycle.open('reactivate', m);
      },
    });

  const columns: DataColumn<TrackerModelDto>[] = [
    { id: 'manufacturer', header: 'Manufacturer', render: (m) => m.manufacturer },
    { id: 'model', header: 'Model', render: (m) => <strong>{m.model}</strong> },
    { id: 'protocol', header: 'Protocol', render: (m) => m.protocol },
    { id: 'adapter', header: 'Adapter', render: (m) => m.adapter },
    {
      id: 'caps',
      header: 'Capabilities',
      render: (m) => String(m.declared_capabilities.length),
      align: 'right',
    },
    {
      id: 'state',
      header: 'State',
      render: (m) => (
        <ActiveChip active={m.approved} activeLabel="Approved" inactiveLabel="Withdrawn" />
      ),
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (m) => <RowActionsMenu label={trackerModelLabel(m)} actions={actionsFor(m, false)} />,
    },
  ];
  const viewed = models.data?.find((m) => m.id === viewingId) ?? null;

  return (
    <Box className="flex flex-col gap-3">
      <Box className="flex flex-wrap items-center gap-3">
        <TextField
          size="small"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
          }}
          placeholder="Search manufacturer, model or protocol"
          slotProps={{
            htmlInput: { 'aria-label': 'Search tracker models' },
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            },
          }}
        />
        <ShowInactiveToggle
          checked={showInactive}
          onChange={setShowInactive}
          label="Show withdrawn"
        />
        <Box className="flex-1" />
        {canManage && (
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => {
              setEditing({ kind: 'new' });
            }}
          >
            Add tracker model
          </Button>
        )}
      </Box>
      <AsyncContent
        resource={models}
        isEmpty={(rows) => rows.length === 0}
        emptyTitle="No tracker models found"
        errorTitle="Could not load tracker models"
      >
        {(rows) => (
          <StaticTable
            ariaLabel="Tracker models"
            columns={columns}
            rows={rows}
            getRowId={(m) => m.id}
            isRowMuted={(m) => !m.approved}
            onRowClick={(m) => {
              setViewingId(m.id);
            }}
          />
        )}
      </AsyncContent>
      {viewed !== null && (
        <DetailsDrawer
          title={trackerModelLabel(viewed)}
          status={
            <ActiveChip active={viewed.approved} activeLabel="Approved" inactiveLabel="Withdrawn" />
          }
          actions={<ActionButtons actions={actionsFor(viewed, true)} />}
          onClose={() => {
            setViewingId(null);
          }}
        >
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Manufacturer', value: viewed.manufacturer },
              { label: 'Model', value: viewed.model },
              { label: 'Protocol', value: viewed.protocol },
              { label: 'Adapter', value: viewed.adapter },
              {
                label: 'Declared capabilities',
                value: viewed.declared_capabilities.map((c) => CAPABILITY_LABELS[c]).join(', '),
              },
              { label: 'Notes', value: viewed.notes ?? '—' },
              { label: 'Version', value: String(viewed.version) },
              {
                label: 'Withdrawn',
                value:
                  viewed.deactivated_at == null
                    ? '—'
                    : `${formatInstant(viewed.deactivated_at)} · ${viewed.deactivation_reason ?? ''}`,
              },
            ]}
          />
        </DetailsDrawer>
      )}
      {editing !== null && (
        <TrackerModelDialog
          {...(editing.kind === 'edit' ? { model: editing.model } : {})}
          onClose={() => {
            setEditing(null);
          }}
          onSaved={(m) => {
            notify.success(`${trackerModelLabel(m)} saved.`);
            models.reload();
          }}
          onReload={models.reload}
        />
      )}
      {lifecycle.dialog}
    </Box>
  );
}
