import Add from '@mui/icons-material/Add';
import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { mixed, object, string, type ObjectSchema } from 'yup';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { inactiveFilter } from '../../../api/lifecycle';
import type { ReasonCodeDto, ReasonKind } from '../../../api/hoursTypes';
import { REASON_KINDS } from '../../../api/services/hoursSchemas';
import { hoursReasonService } from '../../../api/services/hoursService';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { standardRowActions } from '../../../components/lifecycle/rowActions';
import { ShowInactiveToggle } from '../../../components/lifecycle/ShowInactiveToggle';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useLifecycleDialog } from '../../../components/lifecycle/useLifecycleDialog';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useNotify } from '../../../notifications/useNotify';
import { withErrorCode } from '../shared/errorHints';
import { HOURS_ERROR_HINTS, REASON_KIND_LABELS, REASON_KIND_OPTIONS } from './hoursDisplay';

interface ReasonValues {
  kind: ReasonKind | '';
  code: string;
  label: string;
}

const schema: ObjectSchema<ReasonValues> = object({
  kind: mixed<ReasonKind | ''>()
    .default('')
    .oneOf(['', ...REASON_KINDS])
    .defined()
    .test('kind', 'Choose what the reason is for', (v) => v !== ''),
  code: string().trim().required('Code is required').max(32, 'At most 32 characters'),
  label: string().trim().required('Label is required').max(200, 'At most 200 characters'),
});

const label = (r: ReasonCodeDto) => `${r.code} · ${r.label}`;

function ReasonDialogForm({
  record,
  onClose,
  onSaved,
  onReload,
}: {
  record: ReasonCodeDto | null;
  onClose: () => void;
  onSaved: (r: ReasonCodeDto) => void;
  onReload: () => void;
}) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  return (
    <FormDialog<ReasonValues>
      open
      title={record === null ? 'New reason' : `Edit ${label(record)}`}
      initialValues={{
        kind: record?.kind ?? '',
        code: record?.code ?? '',
        label: record?.label ?? '',
      }}
      validationSchema={schema}
      submitLabel={record === null ? 'Create reason' : 'Save changes'}
      onClose={onClose}
      onSubmit={async (v) => {
        try {
          if (record === null) {
            const body = { kind: v.kind as ReasonKind, code: v.code.trim(), label: v.label.trim() };
            onSaved(await hoursReasonService.create(body, keyFor(body)));
          } else {
            const body = { code: v.code.trim(), label: v.label.trim(), version: record.version };
            onSaved(await guard(() => hoursReasonService.update(record.id, body, keyFor(body))));
          }
        } catch (err) {
          throw withErrorCode(err, HOURS_ERROR_HINTS);
        }
      }}
    >
      {stale && (
        <StaleVersionAlert
          onReload={() => {
            onReload();
            onClose();
          }}
        />
      )}
      <FormikSelectField
        name="kind"
        label="Used for"
        options={REASON_KIND_OPTIONS}
        required
        disabled={record !== null}
      />
      <FormikTextField name="code" label="Code" required />
      <FormikTextField name="label" label="Label" required />
    </FormDialog>
  );
}

/** The tenant's reason lists for discounts, credit, transfers and cancellations (tenant data). */
export function HoursReasonsPage() {
  const notify = useNotify();
  const canManage = useCanMutate(PERMISSIONS.tenantHoursReasons);
  const [kind, setKind] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<{ record: ReasonCodeDto | null } | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  const fetchPage = useCallback<FetchPage<ReasonCodeDto>>(
    (query, signal) => hoursReasonService.list(query, signal),
    [],
  );
  const lifecycle = useLifecycleDialog<ReasonCodeDto>({
    labelOf: label,
    noun: 'reason',
    consequences: 'It can no longer be chosen; records that cite it keep it.',
    errorHints: HOURS_ERROR_HINTS,
    deactivate: (r, body, key) =>
      hoursReasonService.deactivate(r.id, { ...body, version: r.version }, key),
    reactivate: (r, body, key) =>
      hoursReasonService.reactivate(r.id, { ...body, version: r.version }, key),
    onDone: (r, k) => {
      notify.success(`${label(r)} ${k === 'deactivate' ? 'deactivated' : 'reactivated'}.`);
      reload();
    },
    onReload: reload,
  });
  const columns: DataColumn<ReasonCodeDto>[] = [
    { id: 'kind', header: 'Used for', render: (r) => REASON_KIND_LABELS[r.kind] },
    { id: 'code', header: 'Code', sortField: 'code', render: (r) => <strong>{r.code}</strong> },
    { id: 'label', header: 'Label', render: (r) => r.label },
    { id: 'state', header: 'State', render: (r) => <ActiveChip active={r.is_active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (r) => (
        <RowActionsMenu
          label={label(r)}
          actions={standardRowActions({
            active: r.is_active,
            canEdit: canManage,
            canChangeState: canManage,
            onEdit: () => {
              setEditing({ record: r });
            },
            onDeactivate: () => {
              lifecycle.open('deactivate', r);
            },
            onReactivate: () => {
              lifecycle.open('reactivate', r);
            },
          })}
        />
      ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Hours reasons"
        subtitle="Your company’s reasons for discounts, credit, transfers and cancellations"
        actions={
          canManage && (
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setEditing({ record: null });
              }}
            >
              New reason
            </Button>
          )
        }
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(r) => r.id}
        searchPlaceholder="Search code or label"
        reloadKey={reloadKey}
        filters={{ kind: kind === '' ? undefined : kind, ...inactiveFilter(showInactive) }}
        emptyTitle="No reasons"
        isRowMuted={(r) => !r.is_active}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Used for"
              value={kind}
              options={REASON_KIND_OPTIONS}
              allLabel="All"
              onChange={setKind}
            />
            <ShowInactiveToggle checked={showInactive} onChange={setShowInactive} />
          </Box>
        }
      />
      {editing !== null && (
        <ReasonDialogForm
          record={editing.record}
          onClose={() => {
            setEditing(null);
          }}
          onSaved={(r) => {
            notify.success(`Reason ${label(r)} saved.`);
            reload();
          }}
          onReload={reload}
        />
      )}
      {lifecycle.dialog}
    </>
  );
}
