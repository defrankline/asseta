import Add from '@mui/icons-material/Add';
import { Box, Button, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import type { MachineReportReasonDto } from '../../../api/machineReportTypes';
import { machineReportReasonService } from '../../../api/services/machineReportService';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import { DetailsDrawer } from '../../../components/lifecycle/DetailsDrawer';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { standardRowActions, type RowAction } from '../../../components/lifecycle/rowActions';
import { ShowInactiveToggle } from '../../../components/lifecycle/ShowInactiveToggle';
import { useLifecycleDialog } from '../../../components/lifecycle/useLifecycleDialog';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNotify } from '../../../notifications/useNotify';
import { REASON_ERROR_HINTS } from './machineReportDisplay';
import { MachineReportReasonDialog } from './MachineReportReasonDialog';

type Editing = { kind: 'new' } | { kind: 'edit'; reason: MachineReportReasonDto } | null;

const labelOf = (r: MachineReportReasonDto) => `${r.name} (${r.code})`;

/**
 * Administration › Machine report reasons: the reasons supervisors give for non-productive hours
 * (transit, breakdown, servicing, …). List, add, edit, deactivate and reactivate.
 */
export function MachineReportReasonsPage() {
  const notify = useNotify();
  const canManage = useCanMutate(PERMISSIONS.tenantMeterReasons);
  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<Editing>(null);
  const [viewing, setViewing] = useState<MachineReportReasonDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = () => {
    setReloadKey((k) => k + 1);
  };
  const load = useCallback(
    (signal: AbortSignal) => machineReportReasonService.list(showInactive, signal),
    [showInactive],
  );
  const res = useAsyncResource(load, [reloadKey]);
  const lifecycle = useLifecycleDialog<MachineReportReasonDto>({
    labelOf,
    noun: 'reason',
    consequences: 'It can no longer be chosen on new reports; past reports keep it.',
    errorHints: REASON_ERROR_HINTS,
    deactivate: (r, body, key) =>
      machineReportReasonService.deactivate(r.id, { ...body, version: r.version }, key),
    reactivate: (r, body, key) =>
      machineReportReasonService.reactivate(r.id, { ...body, version: r.version }, key),
    onDone: (r, action) => {
      notify.success(`${labelOf(r)} ${action === 'deactivate' ? 'deactivated' : 'reactivated'}.`);
      setViewing(null);
      reload();
    },
    onReload: reload,
  });
  const actionsFor = (r: MachineReportReasonDto, inDrawer: boolean): RowAction[] =>
    standardRowActions({
      active: r.is_active,
      canEdit: canManage,
      canChangeState: canManage,
      ...(inDrawer
        ? {}
        : {
            onView: () => {
              setViewing(r);
            },
          }),
      onEdit: () => {
        setViewing(null);
        setEditing({ kind: 'edit', reason: r });
      },
      onDeactivate: () => {
        lifecycle.open('deactivate', r);
      },
      onReactivate: () => {
        lifecycle.open('reactivate', r);
      },
    });
  const columns: DataColumn<MachineReportReasonDto>[] = [
    { id: 'name', header: 'Reason', render: (r) => <strong>{r.name}</strong> },
    { id: 'code', header: 'Code', render: (r) => r.code },
    { id: 'description', header: 'Description', render: (r) => r.description ?? '—' },
    { id: 'state', header: 'State', render: (r) => <ActiveChip active={r.is_active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (r) => <RowActionsMenu label={labelOf(r)} actions={actionsFor(r, false)} />,
    },
  ];
  return (
    <>
      <PageHeader
        title="Machine report reasons"
        subtitle="Reasons supervisors give for non-productive engine hours on machine reports"
        actions={
          canManage ? (
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setEditing({ kind: 'new' });
              }}
            >
              New reason
            </Button>
          ) : undefined
        }
      />
      <Stack spacing={2}>
        <Box>
          <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} />
        </Box>
        <AsyncContent
          resource={res}
          isEmpty={(rows) => rows.length === 0}
          emptyTitle="No reasons"
          emptyDescription="Add the reasons your supervisors use for hours that are not customer work."
          errorTitle="Could not load the reasons"
        >
          {(rows) => (
            <StaticTable<MachineReportReasonDto>
              ariaLabel="Machine report reasons"
              rows={rows}
              getRowId={(r) => r.id}
              columns={columns}
              isRowMuted={(r) => !r.is_active}
              onRowClick={setViewing}
            />
          )}
        </AsyncContent>
      </Stack>
      {viewing !== null && (
        <DetailsDrawer
          title={labelOf(viewing)}
          status={<ActiveChip active={viewing.is_active} />}
          actions={<ActionButtons actions={actionsFor(viewing, true)} />}
          onClose={() => {
            setViewing(null);
          }}
        >
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Code', value: viewing.code },
              { label: 'Name', value: viewing.name },
              { label: 'Description', value: viewing.description ?? '—' },
              { label: 'Version', value: String(viewing.version) },
            ]}
          />
        </DetailsDrawer>
      )}
      {editing !== null && (
        <MachineReportReasonDialog
          {...(editing.kind === 'edit' ? { reason: editing.reason } : {})}
          onClose={() => {
            setEditing(null);
          }}
          onSaved={(r) => {
            notify.success(`${labelOf(r)} saved.`);
            reload();
          }}
          onReload={reload}
        />
      )}
      {lifecycle.dialog}
    </>
  );
}
