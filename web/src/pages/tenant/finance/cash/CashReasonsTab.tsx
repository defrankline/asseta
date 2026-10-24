import Add from '@mui/icons-material/Add';
import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useCanMutate } from '../../../../access/useCanMutate';
import { custodyService } from '../../../../api/services/custodyService';
import type { CashReasonDto } from '../../../../api/custodyTypes';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { ActionButtons } from '../../../../components/lifecycle/ActionButtons';
import { ActiveChip } from '../../../../components/lifecycle/ActiveChip';
import { DetailsDrawer } from '../../../../components/lifecycle/DetailsDrawer';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { standardRowActions, type RowAction } from '../../../../components/lifecycle/rowActions';
import { ShowInactiveToggle } from '../../../../components/lifecycle/ShowInactiveToggle';
import { useLifecycleDialog } from '../../../../components/lifecycle/useLifecycleDialog';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { CUSTODY_ERROR_HINTS, REASON_KIND_LABELS, REASON_KIND_OPTIONS } from './custodyDisplay';
import { ReasonDialog } from './CustodyRequestDialogs';

type Editing = { kind: 'new' } | { kind: 'edit'; reason: CashReasonDto } | null;

const label = (r: CashReasonDto) => `${REASON_KIND_LABELS[r.kind]} · ${r.label}`;

/** The tenant's cash reason lists (variance, write-off, retention, adjustment): tenant data, not code. */
export function CashReasonsTab({ timeZone }: { timeZone: string }) {
  const notify = useNotify();
  const canManage = useCanMutate(PERMISSIONS.tenantFinanceReasonManage);
  const [kind, setKind] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<Editing>(null);
  const [viewing, setViewing] = useState<CashReasonDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = () => {
    setReloadKey((k) => k + 1);
  };
  const fetchPage = useCallback<FetchPage<CashReasonDto>>(
    (query, signal) => custodyService.reasons(query, signal),
    [],
  );
  const lifecycle = useLifecycleDialog<CashReasonDto>({
    labelOf: label,
    noun: 'cash reason',
    consequences: 'It can no longer be chosen; records that used it keep it.',
    errorHints: CUSTODY_ERROR_HINTS,
    deactivate: (r, body, key) =>
      custodyService.deactivateReason(r.id, { ...body, version: r.version }, key),
    reactivate: (r, body, key) =>
      custodyService.reactivateReason(r.id, { ...body, version: r.version }, key),
    onDone: (r, k) => {
      notify.success(`${label(r)} ${k === 'deactivate' ? 'deactivated' : 'reactivated'}.`);
      setViewing(null);
      reload();
    },
    onReload: reload,
  });
  const actionsFor = (r: CashReasonDto, inDrawer: boolean): RowAction[] =>
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
  const columns: DataColumn<CashReasonDto>[] = [
    { id: 'kind', header: 'List', render: (r) => REASON_KIND_LABELS[r.kind] },
    { id: 'label', header: 'Label', render: (r) => <strong>{r.label}</strong> },
    { id: 'description', header: 'Description', render: (r) => r.description ?? '—' },
    { id: 'state', header: 'State', render: (r) => <ActiveChip active={r.is_active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (r) => <RowActionsMenu label={label(r)} actions={actionsFor(r, false)} />,
    },
  ];
  return (
    <Box className="flex flex-col gap-3">
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(r) => r.id}
        searchPlaceholder="Search label"
        reloadKey={reloadKey}
        filters={{
          kind: kind || undefined,
          include_inactive: showInactive ? 'true' : undefined,
        }}
        emptyTitle="No cash reasons"
        emptyDescription="Without a list, people explain variances, write-offs, retentions and adjustments in free text."
        isRowMuted={(r) => !r.is_active}
        onRowClick={setViewing}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="List"
              value={kind}
              options={REASON_KIND_OPTIONS}
              onChange={setKind}
            />
            <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} />
            {canManage && (
              <Button
                variant="outlined"
                startIcon={<Add />}
                onClick={() => {
                  setEditing({ kind: 'new' });
                }}
              >
                New reason
              </Button>
            )}
          </Box>
        }
      />
      {viewing !== null && (
        <DetailsDrawer
          title={label(viewing)}
          status={<ActiveChip active={viewing.is_active} />}
          actions={<ActionButtons actions={actionsFor(viewing, true)} />}
          onClose={() => {
            setViewing(null);
          }}
        >
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'List', value: REASON_KIND_LABELS[viewing.kind] },
              { label: 'Label', value: viewing.label },
              { label: 'Description', value: viewing.description ?? '—' },
              { label: 'Created', value: formatInstantIn(viewing.created_at, timeZone) },
              { label: 'Version', value: String(viewing.version) },
              {
                label: 'Deactivated',
                value:
                  viewing.deactivated_at === null
                    ? '—'
                    : formatInstantIn(viewing.deactivated_at, timeZone),
              },
              { label: 'Deactivation reason', value: viewing.deactivation_reason ?? '—' },
            ]}
          />
        </DetailsDrawer>
      )}
      {editing !== null && (
        <ReasonDialog
          {...(editing.kind === 'edit' ? { reason: editing.reason } : {})}
          onClose={() => {
            setEditing(null);
          }}
          onSaved={(r) => {
            notify.success(`${label(r)} saved.`);
            reload();
          }}
        />
      )}
      {lifecycle.dialog}
    </Box>
  );
}
