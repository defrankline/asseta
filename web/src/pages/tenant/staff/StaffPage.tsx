import Add from '@mui/icons-material/Add';
import { Button, MenuItem, TextField } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { inactiveFilter } from '../../../api/lifecycle';
import { staffService } from '../../../api/services/staffService';
import type { StaffDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { ShowInactiveToggle } from '../../../components/lifecycle/ShowInactiveToggle';
import { staffDetailPath } from '../../../navigation/routes';
import { initialFilter } from '../../../navigation/urlFilters';
import { useNotify } from '../../../notifications/useNotify';
import { STAFF_KIND_OPTIONS, labelOf } from '../shared/display';
import { CreateStaffDialog } from './CreateStaffDialog';
import { useStaffActions } from './useStaffActions';

/** Supervisors and operators: search, kind filter, show inactive, row lifecycle actions. */
export function StaffPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const [creating, setCreating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [params] = useSearchParams();
  const [kind, setKind] = useState(() => initialFilter(params, 'kind', STAFF_KIND_OPTIONS, ''));
  const [showInactive, setShowInactive] = useState(false);
  const refresh = () => {
    setReloadKey((k) => k + 1);
  };
  const view = (s: StaffDto) => {
    void navigate(staffDetailPath(s.id));
  };
  const { actionsFor, dialogs } = useStaffActions({
    onChanged: refresh,
    onReload: refresh,
    onView: view,
  });
  const filters = useMemo(
    () => ({ kind: kind || undefined, ...inactiveFilter(showInactive) }),
    [kind, showInactive],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      staffService.list(
        { page: q.page, page_size: q.page_size, q: q.q, filters: q.filters },
        signal,
      ),
    [],
  );
  const columns: DataColumn<StaffDto>[] = [
    { id: 'name', header: 'Name', render: (s) => <strong>{s.full_name}</strong> },
    { id: 'kind', header: 'Kind', render: (s) => labelOf(STAFF_KIND_OPTIONS, s.kind) },
    { id: 'code', header: 'Employee code', render: (s) => s.employee_code ?? '—' },
    { id: 'phone', header: 'Phone', render: (s) => s.phone ?? '—' },
    {
      id: 'login',
      header: 'App login',
      render: (s) =>
        s.keycloak_subject !== null ? (
          <StatusChip status="LINKED" tones={{ LINKED: 'success' }} label="Linked" />
        ) : (
          <StatusChip status="NOT_LINKED" label="Not linked" />
        ),
    },
    { id: 'active', header: 'State', render: (s) => <ActiveChip active={s.is_active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (s) => <RowActionsMenu label={s.full_name} actions={actionsFor(s)} />,
    },
  ];

  return (
    <>
      <PageHeader
        title="Staff"
        subtitle="Supervisors and operators who can be assigned to machines"
        actions={
          <CanMutate permission={PERMISSIONS.tenantStaffWrite}>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setCreating(true);
              }}
            >
              New staff member
            </Button>
          </CanMutate>
        }
      />
      <ServerDataTable<StaffDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(s) => s.id}
        filters={filters}
        searchPlaceholder="Search name, employee code or phone"
        emptyTitle="No staff members found"
        reloadKey={reloadKey}
        isRowMuted={(s) => !s.is_active}
        onRowClick={view}
        toolbar={
          <>
            <TextField
              select
              size="small"
              label="Kind"
              value={kind}
              onChange={(e) => {
                setKind(e.target.value);
              }}
              sx={{ minWidth: 160 }}
            >
              <MenuItem value="">All kinds</MenuItem>
              {STAFF_KIND_OPTIONS.map((o) => (
                <MenuItem key={o.value} value={o.value}>
                  {o.label}
                </MenuItem>
              ))}
            </TextField>
            <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} />
          </>
        }
      />
      {creating && (
        <CreateStaffDialog
          onClose={() => {
            setCreating(false);
          }}
          onCreated={(s) => {
            notify.success(`${s.full_name} added.`);
            refresh();
          }}
        />
      )}
      {dialogs}
    </>
  );
}
