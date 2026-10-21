import Add from '@mui/icons-material/Add';
import { Button, MenuItem, TextField } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { staffService } from '../../../api/services/staffService';
import type { StaffDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useNotify } from '../../../notifications/useNotify';
import { STAFF_KIND_OPTIONS, labelOf } from '../shared/display';
import { CreateStaffDialog } from './CreateStaffDialog';

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
  {
    id: 'active',
    header: 'Active',
    render: (s) =>
      s.is_active ? (
        <StatusChip status="ACTIVE" tones={{ ACTIVE: 'success' }} label="Active" />
      ) : (
        <StatusChip status="INACTIVE" label="Inactive" />
      ),
  },
];

export function StaffPage() {
  const notify = useNotify();
  const [creating, setCreating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [kind, setKind] = useState('');
  const filters = useMemo(() => ({ kind: kind || undefined }), [kind]);
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      staffService.list(
        { page: q.page, page_size: q.page_size, q: q.q, filters: q.filters },
        signal,
      ),
    [],
  );

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
        searchPlaceholder="Search staff"
        emptyTitle="No staff members found"
        reloadKey={reloadKey}
        toolbar={
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
        }
      />
      {creating && (
        <CreateStaffDialog
          onClose={() => {
            setCreating(false);
          }}
          onCreated={(s) => {
            notify.success(`${s.full_name} added.`);
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
