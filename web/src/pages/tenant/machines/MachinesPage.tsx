import Add from '@mui/icons-material/Add';
import { Button, MenuItem, TextField } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { machineService } from '../../../api/services/machineService';
import type { MachineDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { machineDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { formatMoney } from '../../../utils/money';
import {
  MACHINE_STATUS_OPTIONS,
  MACHINE_STATUS_TONES,
  OWNERSHIP_OPTIONS,
  labelOf,
  machineLabel,
} from '../shared/display';
import { CreateMachineDialog } from './CreateMachineDialog';
import { EnrollMachineDialog } from './EnrollMachineDialog';

const ALL = '';

export function MachinesPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const canEnroll = useCanMutate(PERMISSIONS.tenantBillingEnroll);
  const [creating, setCreating] = useState(false);
  const [enrolling, setEnrolling] = useState<MachineDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [status, setStatus] = useState(ALL);
  const [categoryId, setCategoryId] = useState(ALL);

  const loadCategories = useCallback(
    (signal: AbortSignal) => machineService.listCategories(signal),
    [],
  );
  const categories = useAsyncResource(loadCategories, [reloadKey]);
  const categoryName = useMemo(() => {
    const names = new Map((categories.data ?? []).map((c) => [c.id, c.name]));
    return (id: string | null) => (id === null ? '—' : (names.get(id) ?? '—'));
  }, [categories.data]);

  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      machineService.list(
        { page: q.page, page_size: q.page_size, q: q.q, filters: q.filters },
        signal,
      ),
    [],
  );
  const filters = useMemo(
    () => ({ status: status || undefined, category_id: categoryId || undefined }),
    [status, categoryId],
  );

  const columns: DataColumn<MachineDto>[] = [
    { id: 'asset_code', header: 'Asset code', render: (m) => <strong>{m.asset_code}</strong> },
    { id: 'name', header: 'Name', render: (m) => m.name },
    { id: 'category', header: 'Category', render: (m) => categoryName(m.category_id) },
    {
      id: 'make',
      header: 'Manufacturer / model',
      render: (m) => [m.manufacturer, m.model].filter((x) => x !== null).join(' ') || '—',
    },
    {
      id: 'ownership',
      header: 'Ownership',
      render: (m) => labelOf(OWNERSHIP_OPTIONS, m.ownership),
    },
    {
      id: 'status',
      header: 'Status',
      render: (m) => (
        <StatusChip
          status={m.status}
          tones={MACHINE_STATUS_TONES}
          label={labelOf(MACHINE_STATUS_OPTIONS, m.status)}
        />
      ),
    },
    { id: 'meter', header: 'Meter dp', align: 'right', render: (m) => m.meter_decimal_places },
    ...(canEnroll
      ? [
          {
            id: 'actions',
            header: '',
            align: 'right' as const,
            render: (m: MachineDto) =>
              m.status === 'DISPOSED' ? null : (
                <Button
                  size="small"
                  aria-label={`Enroll ${machineLabel(m)} as billable asset`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setEnrolling(m);
                  }}
                >
                  Enroll
                </Button>
              ),
          },
        ]
      : []),
  ];

  const toolbar = (
    <>
      <TextField
        select
        size="small"
        label="Status"
        value={status}
        onChange={(e) => {
          setStatus(e.target.value);
        }}
        sx={{ minWidth: 160 }}
      >
        <MenuItem value={ALL}>All statuses</MenuItem>
        {MACHINE_STATUS_OPTIONS.map((o) => (
          <MenuItem key={o.value} value={o.value}>
            {o.label}
          </MenuItem>
        ))}
      </TextField>
      <TextField
        select
        size="small"
        label="Category"
        value={categoryId}
        onChange={(e) => {
          setCategoryId(e.target.value);
        }}
        sx={{ minWidth: 180 }}
      >
        <MenuItem value={ALL}>All categories</MenuItem>
        {(categories.data ?? []).map((c) => (
          <MenuItem key={c.id} value={c.id}>
            {c.name}
          </MenuItem>
        ))}
      </TextField>
    </>
  );

  return (
    <>
      <PageHeader
        title="Machines"
        subtitle="Equipment registry: individual assets, categories and operating areas"
        actions={
          <CanMutate permission={PERMISSIONS.tenantMachineWrite}>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setCreating(true);
              }}
            >
              New machine
            </Button>
          </CanMutate>
        }
      />
      <ServerDataTable<MachineDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(m) => m.id}
        filters={filters}
        toolbar={toolbar}
        searchPlaceholder="Search asset code or name"
        emptyTitle="No machines found"
        emptyDescription="Register machines to track and bill them."
        reloadKey={reloadKey}
        onRowClick={(m) => {
          void navigate(machineDetailPath(m.id));
        }}
      />
      {creating && (
        <CreateMachineDialog
          onClose={() => {
            setCreating(false);
          }}
          onCreated={(m) => {
            notify.success(`Machine ${m.asset_code} created.`);
            setReloadKey((k) => k + 1);
          }}
        />
      )}
      {enrolling !== null && (
        <EnrollMachineDialog
          machine={enrolling}
          onClose={() => {
            setEnrolling(null);
          }}
          onEnrolled={(r) => {
            notify.success(
              r.charge === null
                ? `${r.enrollment.asset_label} enrolled as a billable asset.`
                : `${r.enrollment.asset_label} enrolled; pending ${formatMoney(r.charge.amount, r.charge.currency)} recorded.`,
            );
          }}
        />
      )}
    </>
  );
}
