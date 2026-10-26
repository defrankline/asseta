import Add from '@mui/icons-material/Add';
import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { inactiveFilter } from '../../../api/lifecycle';
import { revenueService } from '../../../api/services/revenueService';
import type { RevenueReasonDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import { DetailsDrawer } from '../../../components/lifecycle/DetailsDrawer';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { standardRowActions, type RowAction } from '../../../components/lifecycle/rowActions';
import { ShowInactiveToggle } from '../../../components/lifecycle/ShowInactiveToggle';
import { useLifecycleDialog } from '../../../components/lifecycle/useLifecycleDialog';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { REVENUE_ERROR_HINTS } from './revenueDisplay';
import { revenueReasonLabel } from './revenueLookups';
import { RevenueReasonDialog } from './RevenueReasonDialog';

type Editing = { kind: 'new' } | { kind: 'edit'; reason: RevenueReasonDto } | null;

/**
 * The tenant's reasons for explaining revenue differences and non-revenue time (e.g. movement
 * between sites, customer dispute, rate agreed later). Search, create, edit, deactivate.
 */
export function RevenueReasonsPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const canManage = useCanMutate(PERMISSIONS.tenantRevenueDecide);
  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<Editing>(null);
  const [viewing, setViewing] = useState<RevenueReasonDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = () => {
    setReloadKey((k) => k + 1);
  };
  const fetchPage = useCallback<FetchPage<RevenueReasonDto>>(
    (query, signal) => revenueService.listReasons(query, signal),
    [],
  );
  const lifecycle = useLifecycleDialog<RevenueReasonDto>({
    labelOf: revenueReasonLabel,
    noun: 'reason',
    consequences: 'It can no longer be chosen for new explanations; past explanations keep it.',
    errorHints: REVENUE_ERROR_HINTS,
    deactivate: (r, body, key) =>
      revenueService.deactivateReason(r.id, { ...body, version: r.version }, key),
    reactivate: (r, body, key) =>
      revenueService.reactivateReason(r.id, { ...body, version: r.version }, key),
    onDone: (r, action) => {
      notify.success(
        `${revenueReasonLabel(r)} ${action === 'deactivate' ? 'deactivated' : 'reactivated'}.`,
      );
      setViewing(null);
      reload();
    },
    onReload: reload,
  });
  const actionsFor = (r: RevenueReasonDto, inDrawer: boolean): RowAction[] =>
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
  const columns: DataColumn<RevenueReasonDto>[] = [
    { id: 'code', header: 'Code', render: (r) => <strong>{r.code}</strong> },
    { id: 'name', header: 'Name', render: (r) => r.name },
    { id: 'description', header: 'Description', render: (r) => r.description ?? '—' },
    { id: 'state', header: 'State', render: (r) => <ActiveChip active={r.is_active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (r) => (
        <RowActionsMenu label={revenueReasonLabel(r)} actions={actionsFor(r, false)} />
      ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Revenue reasons"
        subtitle="Your list of reasons for explaining revenue differences and non-revenue time"
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
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(r) => r.id}
        searchPlaceholder="Search code or name"
        reloadKey={reloadKey}
        filters={inactiveFilter(showInactive)}
        emptyTitle="No reasons"
        emptyDescription="Add the reasons your organisation uses to explain revenue differences."
        isRowMuted={(r) => !r.is_active}
        onRowClick={setViewing}
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} />
          </Box>
        }
      />
      {viewing !== null && (
        <DetailsDrawer
          title={revenueReasonLabel(viewing)}
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
              {
                label: 'Deactivated',
                value: formatInstantIn(viewing.deactivated_at ?? null, timeZone),
              },
              { label: 'Deactivation reason', value: viewing.deactivation_reason ?? '—' },
            ]}
          />
        </DetailsDrawer>
      )}
      {editing !== null && (
        <RevenueReasonDialog
          {...(editing.kind === 'edit' ? { reason: editing.reason } : {})}
          onClose={() => {
            setEditing(null);
          }}
          onSaved={(r) => {
            notify.success(`${revenueReasonLabel(r)} saved.`);
            reload();
          }}
          onReload={reload}
        />
      )}
      {lifecycle.dialog}
    </>
  );
}
