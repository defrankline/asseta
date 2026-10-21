import Add from '@mui/icons-material/Add';
import SearchIcon from '@mui/icons-material/Search';
import { Box, Button, InputAdornment, Paper, TextField } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { expenseCategoryService } from '../../../api/services/expenseCategoryService';
import type { ExpenseCategoryDto } from '../../../api/types';
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
import { useDebouncedValue } from '../../../hooks/useDebouncedValue';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { ROUTES } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { ExpenseCategoryDialog } from './ExpenseCategoryDialog';
import { EXPENSE_CATEGORY_HINTS } from './expenseCategoryHints';

type Editing = { kind: 'new' } | { kind: 'edit'; category: ExpenseCategoryDto } | null;

const label = (c: ExpenseCategoryDto) => `${c.code} · ${c.name}`;

/** Expense categories used by expense and fuel records: search, create, edit, deactivate. */
export function ExpenseCategoriesPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const canManage = useCanMutate(PERMISSIONS.tenantExpenseCategoryManage);
  const [search, setSearch] = useState('');
  const q = useDebouncedValue(search.trim(), 300);
  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<Editing>(null);
  const [viewingId, setViewingId] = useState<string | null>(null);
  const load = useCallback(
    (signal: AbortSignal) => expenseCategoryService.list(signal, q, showInactive),
    [q, showInactive],
  );
  const categories = useAsyncResource(load);
  const lifecycle = useLifecycleDialog<ExpenseCategoryDto>({
    labelOf: label,
    noun: 'expense category',
    consequences: 'New expenses can no longer be recorded against it; past expenses keep it.',
    errorHints: EXPENSE_CATEGORY_HINTS,
    deactivate: (c, body, key) =>
      expenseCategoryService.deactivate(c.id, { ...body, version: c.version }, key),
    reactivate: (c, body, key) =>
      expenseCategoryService.reactivate(c.id, { ...body, version: c.version }, key),
    onDone: (c, kind) => {
      notify.success(`${label(c)} ${kind === 'deactivate' ? 'deactivated' : 'reactivated'}.`);
      categories.reload();
    },
    onReload: categories.reload,
  });

  const actionsFor = (c: ExpenseCategoryDto, inDrawer: boolean): RowAction[] =>
    standardRowActions({
      active: c.is_active,
      canEdit: canManage,
      canChangeState: canManage,
      ...(inDrawer
        ? {}
        : {
            onView: () => {
              setViewingId(c.id);
            },
          }),
      onEdit: () => {
        setViewingId(null);
        setEditing({ kind: 'edit', category: c });
      },
      onDeactivate: () => {
        lifecycle.open('deactivate', c);
      },
      onReactivate: () => {
        lifecycle.open('reactivate', c);
      },
    });

  const columns: DataColumn<ExpenseCategoryDto>[] = [
    { id: 'code', header: 'Code', render: (c) => <strong>{c.code}</strong> },
    { id: 'name', header: 'Name', render: (c) => c.name },
    { id: 'state', header: 'State', render: (c) => <ActiveChip active={c.is_active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (c) => <RowActionsMenu label={label(c)} actions={actionsFor(c, false)} />,
    },
  ];
  const viewed = categories.data?.find((c) => c.id === viewingId) ?? null;

  return (
    <>
      <PageHeader
        title="Expense categories"
        subtitle="Categories used when recording expenses and fuel"
        actions={
          <Box className="flex gap-2">
            <Button component={RouterLink} to={ROUTES.tenantExpenses} variant="outlined">
              Expenses &amp; fuel
            </Button>
            {canManage && (
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={() => {
                  setEditing({ kind: 'new' });
                }}
              >
                New category
              </Button>
            )}
          </Box>
        }
      />
      <Paper variant="outlined">
        <Box className="flex flex-wrap items-center gap-3 p-3">
          <TextField
            size="small"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
            }}
            placeholder="Search code or name"
            slotProps={{
              htmlInput: { 'aria-label': 'Search code or name' },
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
              },
            }}
          />
          <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} />
        </Box>
        <AsyncContent
          resource={categories}
          isEmpty={(rows) => rows.length === 0}
          emptyTitle="No expense categories found"
          errorTitle="Could not load expense categories"
        >
          {(rows) => (
            <StaticTable
              ariaLabel="Expense categories"
              columns={columns}
              rows={rows}
              getRowId={(c) => c.id}
              isRowMuted={(c) => !c.is_active}
              onRowClick={(c) => {
                setViewingId(c.id);
              }}
            />
          )}
        </AsyncContent>
      </Paper>
      {viewed !== null && (
        <DetailsDrawer
          title={label(viewed)}
          status={<ActiveChip active={viewed.is_active} />}
          actions={<ActionButtons actions={actionsFor(viewed, true)} />}
          onClose={() => {
            setViewingId(null);
          }}
        >
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Code', value: viewed.code },
              { label: 'Name', value: viewed.name },
              { label: 'Version', value: String(viewed.version) },
              {
                label: 'Deactivated',
                value:
                  viewed.deactivated_at == null
                    ? '—'
                    : formatInstantIn(viewed.deactivated_at, timeZone),
              },
              { label: 'Deactivation reason', value: viewed.deactivation_reason ?? '—' },
            ]}
          />
        </DetailsDrawer>
      )}
      {editing !== null && (
        <ExpenseCategoryDialog
          {...(editing.kind === 'edit' ? { category: editing.category } : {})}
          onClose={() => {
            setEditing(null);
          }}
          onSaved={(c) => {
            notify.success(`Expense category ${label(c)} saved.`);
            categories.reload();
          }}
          onReload={categories.reload}
        />
      )}
      {lifecycle.dialog}
    </>
  );
}
