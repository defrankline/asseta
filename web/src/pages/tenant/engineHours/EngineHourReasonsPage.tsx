import Add from '@mui/icons-material/Add';
import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { inactiveFilter } from '../../../api/lifecycle';
import { engineHoursService } from '../../../api/services/engineHoursService';
import type { EngineHourReasonDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
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
import { EngineHourReasonDialog } from './EngineHourReasonDialog';
import {
  ENGINE_HOURS_ERROR_HINTS,
  REASON_KIND_LABELS,
  REASON_KIND_OPTIONS,
} from './engineHoursDisplay';
import { reasonLabel } from './engineHoursLookups';

type Editing = { kind: 'new' } | { kind: 'edit'; reason: EngineHourReasonDto } | null;

/**
 * Tenant lists used to explain engine hours: non-customer activity categories (maintenance,
 * relocation, testing, company work, …) and variance reasons. Search, create, edit, deactivate.
 */
export function EngineHourReasonsPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const canManage = useCanMutate(PERMISSIONS.tenantMeterReasons);
  const [kind, setKind] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<Editing>(null);
  const [viewing, setViewing] = useState<EngineHourReasonDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = () => {
    setReloadKey((k) => k + 1);
  };
  const fetchPage = useCallback<FetchPage<EngineHourReasonDto>>(
    (query, signal) => engineHoursService.listReasons(query, signal),
    [],
  );
  const lifecycle = useLifecycleDialog<EngineHourReasonDto>({
    labelOf: reasonLabel,
    noun: 'list entry',
    consequences: 'It can no longer be chosen for new explanations; past explanations keep it.',
    errorHints: ENGINE_HOURS_ERROR_HINTS,
    deactivate: (r, body, key) =>
      engineHoursService.deactivateReason(r.id, { ...body, version: r.version }, key),
    reactivate: (r, body, key) =>
      engineHoursService.reactivateReason(r.id, { ...body, version: r.version }, key),
    onDone: (r, action) => {
      notify.success(
        `${reasonLabel(r)} ${action === 'deactivate' ? 'deactivated' : 'reactivated'}.`,
      );
      setViewing(null);
      reload();
    },
    onReload: reload,
  });
  const actionsFor = (r: EngineHourReasonDto, inDrawer: boolean): RowAction[] =>
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
  const columns: DataColumn<EngineHourReasonDto>[] = [
    { id: 'code', header: 'Code', render: (r) => <strong>{r.code}</strong> },
    { id: 'name', header: 'Name', render: (r) => r.name },
    { id: 'kind', header: 'List', render: (r) => REASON_KIND_LABELS[r.kind] },
    { id: 'state', header: 'State', render: (r) => <ActiveChip active={r.is_active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (r) => <RowActionsMenu label={reasonLabel(r)} actions={actionsFor(r, false)} />,
    },
  ];
  return (
    <>
      <PageHeader
        title="Engine-hour reasons"
        subtitle="Your lists for explaining engine hours: non-customer activity categories and variance reasons"
        actions={
          canManage ? (
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setEditing({ kind: 'new' });
              }}
            >
              New entry
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
        filters={{ kind: kind || undefined, ...inactiveFilter(showInactive) }}
        emptyTitle="No entries"
        emptyDescription="Add the categories and reasons your organisation uses to explain engine hours."
        isRowMuted={(r) => !r.is_active}
        onRowClick={setViewing}
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="List"
              value={kind}
              options={REASON_KIND_OPTIONS}
              allLabel="Both lists"
              onChange={setKind}
              minWidth={240}
            />
            <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} />
          </Box>
        }
      />
      {viewing !== null && (
        <DetailsDrawer
          title={reasonLabel(viewing)}
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
        <EngineHourReasonDialog
          {...(editing.kind === 'edit'
            ? { reason: editing.reason }
            : kind === 'NON_CUSTOMER_CATEGORY' || kind === 'VARIANCE_REASON'
              ? { defaultKind: kind }
              : {})}
          onClose={() => {
            setEditing(null);
          }}
          onSaved={(r) => {
            notify.success(`${reasonLabel(r)} saved.`);
            reload();
          }}
          onReload={reload}
        />
      )}
      {lifecycle.dialog}
    </>
  );
}
