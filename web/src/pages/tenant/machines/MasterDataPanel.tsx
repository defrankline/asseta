import Add from '@mui/icons-material/Add';
import SearchIcon from '@mui/icons-material/Search';
import { Box, Button, InputAdornment, Paper, TextField } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import type { LifecycleReasonIn } from '../../../api/lifecycle';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid, type KeyValueItem } from '../../../components/display/KeyValueGrid';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import { DetailsDrawer } from '../../../components/lifecycle/DetailsDrawer';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { standardRowActions } from '../../../components/lifecycle/rowActions';
import { ShowInactiveToggle } from '../../../components/lifecycle/ShowInactiveToggle';
import { useLifecycleDialog } from '../../../components/lifecycle/useLifecycleDialog';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDebouncedValue } from '../../../hooks/useDebouncedValue';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';

export interface MasterRecord {
  id: string;
  is_active: boolean;
  version: number;
  deactivated_at: string | null;
  deactivation_reason: string | null;
}

export interface RecordFormProps<T> {
  /** `null` creates a new record. */
  record: T | null;
  onClose: () => void;
  onSaved: (record: T) => void;
  onReload: () => void;
}

type LifecycleCall<T> = (id: string, body: LifecycleReasonIn, key: string) => Promise<T>;

interface MasterDataPanelProps<T extends MasterRecord> {
  /** Entity noun, e.g. `machine category`. */
  noun: string;
  searchPlaceholder: string;
  createLabel: string;
  emptyTitle: string;
  /** Server search (`q`) and the include-inactive flag; never filtered in the browser. */
  load: (signal: AbortSignal, q: string | undefined, includeInactive: boolean) => Promise<T[]>;
  columns: readonly DataColumn<T>[];
  labelOf: (record: T) => string;
  detailItems: (record: T) => KeyValueItem[];
  canWrite: boolean;
  renderForm: (props: RecordFormProps<T>) => ReactNode;
  deactivate: LifecycleCall<T>;
  reactivate: LifecycleCall<T>;
  errorHints?: Readonly<Record<string, string>>;
  consequences?: ReactNode;
}

/**
 * Small master-data list (unpaged, server-searched): view drawer, create, edit, deactivate /
 * reactivate with reason and a "Show inactive" toggle.
 */
export function MasterDataPanel<T extends MasterRecord>(props: MasterDataPanelProps<T>) {
  const { noun, load, labelOf, canWrite } = props;
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const [search, setSearch] = useState('');
  const q = useDebouncedValue(search.trim(), 300);
  const [showInactive, setShowInactive] = useState(false);
  const [viewingId, setViewingId] = useState<string | null>(null);
  const [form, setForm] = useState<{ record: T | null } | null>(null);
  const fetch = useCallback(
    (signal: AbortSignal) => load(signal, q === '' ? undefined : q, showInactive),
    [load, q, showInactive],
  );
  const resource = useAsyncResource(fetch, [q, showInactive]);
  const lifecycle = useLifecycleDialog<T>({
    labelOf,
    noun,
    deactivate: (r, body, key) => props.deactivate(r.id, { ...body, version: r.version }, key),
    reactivate: (r, body, key) => props.reactivate(r.id, { ...body, version: r.version }, key),
    onReload: resource.reload,
    onDone: (r, kind) => {
      notify.success(`${labelOf(r)} ${kind === 'deactivate' ? 'deactivated' : 'reactivated'}.`);
      resource.reload();
    },
    ...(props.errorHints !== undefined ? { errorHints: props.errorHints } : {}),
    ...(props.consequences !== undefined ? { consequences: props.consequences } : {}),
  });

  const actionsFor = (r: T, inDrawer: boolean) =>
    standardRowActions({
      active: r.is_active,
      canEdit: canWrite,
      canChangeState: canWrite,
      ...(inDrawer
        ? {}
        : {
            onView: () => {
              setViewingId(r.id);
            },
          }),
      onEdit: () => {
        setViewingId(null);
        setForm({ record: r });
      },
      onDeactivate: () => {
        lifecycle.open('deactivate', r);
      },
      onReactivate: () => {
        lifecycle.open('reactivate', r);
      },
    });

  const columns: DataColumn<T>[] = [
    ...props.columns,
    { id: 'state', header: 'State', render: (r) => <ActiveChip active={r.is_active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (r) => <RowActionsMenu label={labelOf(r)} actions={actionsFor(r, false)} />,
    },
  ];
  const viewing = resource.data?.find((r) => r.id === viewingId) ?? null;

  return (
    <Paper variant="outlined">
      <Box className="flex flex-wrap items-center gap-3 p-3">
        <TextField
          size="small"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
          }}
          placeholder={props.searchPlaceholder}
          slotProps={{
            htmlInput: { 'aria-label': props.searchPlaceholder },
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
        <Box className="flex-1" />
        {canWrite && (
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => {
              setForm({ record: null });
            }}
          >
            {props.createLabel}
          </Button>
        )}
      </Box>
      <Box className="px-3 pb-3">
        <AsyncContent
          resource={resource}
          isEmpty={(rows) => rows.length === 0}
          emptyTitle={props.emptyTitle}
        >
          {(rows) => (
            <StaticTable
              ariaLabel={props.emptyTitle}
              columns={columns}
              rows={rows}
              getRowId={(r) => r.id}
              isRowMuted={(r) => !r.is_active}
              onRowClick={(r) => {
                setViewingId(r.id);
              }}
            />
          )}
        </AsyncContent>
      </Box>
      {viewing !== null && (
        <DetailsDrawer
          title={labelOf(viewing)}
          status={<ActiveChip active={viewing.is_active} />}
          actions={<ActionButtons actions={actionsFor(viewing, true)} />}
          onClose={() => {
            setViewingId(null);
          }}
        >
          <KeyValueGrid
            columns={2}
            items={[
              ...props.detailItems(viewing),
              ...(viewing.is_active
                ? []
                : [
                    {
                      label: 'Deactivated',
                      value:
                        viewing.deactivated_at === null
                          ? '—'
                          : formatInstantIn(viewing.deactivated_at, timeZone),
                    },
                    { label: 'Reason', value: viewing.deactivation_reason ?? '—' },
                  ]),
              { label: 'Version', value: String(viewing.version) },
            ]}
          />
        </DetailsDrawer>
      )}
      {form !== null &&
        props.renderForm({
          record: form.record,
          onClose: () => {
            setForm(null);
          },
          onSaved: (r) => {
            notify.success(`${labelOf(r)} saved.`);
            resource.reload();
          },
          onReload: resource.reload,
        })}
      {lifecycle.dialog}
    </Paper>
  );
}
