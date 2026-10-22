import Add from '@mui/icons-material/Add';
import { Box, Button, MenuItem, TextField } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { inactiveFilter } from '../../../api/lifecycle';
import { machineService } from '../../../api/services/machineService';
import type { CategoryDto, MachineDto } from '../../../api/types';
import { ExportMenu } from '../../../components/data/ExportMenu';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { ShowInactiveToggle } from '../../../components/lifecycle/ShowInactiveToggle';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { machineDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import {
  MACHINE_STATUS_OPTIONS,
  MACHINE_STATUS_TONES,
  OWNERSHIP_OPTIONS,
  labelOf,
  machineLabel,
} from '../shared/display';
import { CategoryFilter } from '../shared/lookupPickers';
import { CreateMachineDialog } from './CreateMachineDialog';
import { useMachineActions } from './useMachineActions';

const ALL = '';

/** Machine registry list: search, status / category filters, show retired, row actions. */
export function MachineListPanel() {
  const navigate = useNavigate();
  const notify = useNotify();
  const [creating, setCreating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const refresh = () => {
    setReloadKey((k) => k + 1);
  };
  const { actionsFor, dialogs } = useMachineActions({
    onChanged: refresh,
    onReload: refresh,
    onView: (m) => {
      void navigate(machineDetailPath(m.id));
    },
  });
  const [status, setStatus] = useState(ALL);
  const [showInactive, setShowInactive] = useState(false);
  const [category, setCategory] = useState<CategoryDto | null>(null);
  const [search, setSearch] = useState('');

  const loadCategories = useCallback(
    (signal: AbortSignal) => machineService.listCategories(signal, undefined, true),
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
    () => ({
      status: status || undefined,
      category_id: category?.id,
      // An explicit status filter (e.g. Disposed) overrides the default hiding of retired machines.
      ...inactiveFilter(showInactive),
    }),
    [status, category, showInactive],
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
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (m) => <RowActionsMenu label={machineLabel(m)} actions={actionsFor(m)} />,
    },
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
      <Box sx={{ minWidth: 220 }}>
        <CategoryFilter label="Category" value={category} onChange={setCategory} />
      </Box>
      <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} label="Show retired" />
    </>
  );

  return (
    <>
      <Box className="mb-3 flex flex-wrap justify-end gap-2">
        <ExportMenu
          reports={[
            { code: 'fleet', filters: { q: search, machine_status: status === ALL ? '' : status } },
          ]}
        />
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
      </Box>
      <ServerDataTable<MachineDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(m) => m.id}
        filters={filters}
        toolbar={toolbar}
        searchPlaceholder="Search asset code or name"
        onSearchChange={setSearch}
        emptyTitle="No machines found"
        emptyDescription="Register machines to track and bill them."
        reloadKey={reloadKey}
        isRowMuted={(m) => m.status === 'DISPOSED'}
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
            refresh();
          }}
        />
      )}
      {dialogs}
    </>
  );
}
