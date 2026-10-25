import {
  Alert,
  Box,
  Button,
  Paper,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useNavigate, useParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { accountabilityService } from '../../../api/services/accountabilityService';
import type { SyncConflictDto } from '../../../api/custodyTypes';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip, type StatusTone } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { ROUTES, syncConflictDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import { withErrorCode } from '../shared/errorHints';
import { CUSTODY_ERROR_HINTS } from '../finance/cash/custodyDisplay';
import {
  syncResolutionSchema,
  toSyncResolutionPayload,
  type SyncResolutionValues,
} from '../finance/cash/custodyForms';
import { PersonName } from '../shared/PersonName';
import { useMyUserId } from '../shared/useFinanceLabels';

const STATUS_LABELS: Readonly<Record<SyncConflictDto['status'], string>> = {
  CONFLICT: 'Conflict',
  REJECTED: 'Rejected',
};
const STATUS_TONES: Readonly<Record<SyncConflictDto['status'], StatusTone>> = {
  CONFLICT: 'warning',
  REJECTED: 'error',
};
const STATUS_OPTIONS = [
  { value: 'CONFLICT', label: 'Conflict' },
  { value: 'REJECTED', label: 'Rejected' },
];
const OUTCOME_LABELS = { DISMISSED: 'Dismissed', RECAPTURED: 'Re-captured' } as const;
const OUTCOME_OPTIONS = [
  { value: 'DISMISSED', label: 'Dismiss (no further action)' },
  { value: 'RECAPTURED', label: 'Re-captured (recorded again correctly)' },
];

type View = 'open' | 'resolved' | 'all';

const statusChip = (c: SyncConflictDto) => (
  <StatusChip status={c.status} tones={STATUS_TONES} label={STATUS_LABELS[c.status]} />
);
const outcomeText = (c: SyncConflictDto) =>
  c.resolution === null ? 'Awaiting review' : OUTCOME_LABELS[c.resolution.outcome];
const submitter = (c: SyncConflictDto) =>
  c.submitted_by_name ?? <PersonName userId={c.submitted_by} />;

/** Record the office's outcome once (never the person who submitted the operation). */
function ResolveDialog({
  conflict,
  onDone,
  onClose,
}: {
  conflict: SyncConflictDto;
  onDone: (c: SyncConflictDto) => void;
  onClose: () => void;
}) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<SyncResolutionValues>
      open
      title="Resolve offline operation"
      initialValues={{
        outcome: '',
        reason: '',
        recaptured_entity_type: '',
        recaptured_entity_id: '',
      }}
      validationSchema={syncResolutionSchema}
      submitLabel="Record outcome"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = toSyncResolutionPayload(v);
        try {
          onDone(
            await accountabilityService.resolveSyncConflict(
              conflict.operation_id,
              body,
              keyFor(body),
            ),
          );
        } catch (err) {
          throw withErrorCode(err, CUSTODY_ERROR_HINTS);
        }
      }}
    >
      {(f) => (
        <>
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Operation', value: humanize(conflict.op_type) },
              { label: 'Submitted by', value: submitter(conflict) },
              {
                label: 'Why not applied',
                value: conflict.error_message ?? conflict.error_code ?? '—',
              },
            ]}
          />
          <FormikSelectField name="outcome" label="Outcome" options={OUTCOME_OPTIONS} required />
          <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
          {f.values.outcome === 'RECAPTURED' && (
            <>
              <FormikTextField
                name="recaptured_entity_type"
                label="Re-captured record type (optional, e.g. meter_capture)"
              />
              <FormikTextField
                name="recaptured_entity_id"
                label="Re-captured record id (optional)"
              />
            </>
          )}
        </>
      )}
    </FormDialog>
  );
}

/** Offline field operations the server did not apply, with their evidence; resolve each once. */
export function SyncConflictsPage() {
  const timeZone = useDisplayTimeZone();
  const navigate = useNavigate();
  const notify = useNotify();
  const me = useMyUserId();
  const canResolve = useCanMutate(PERMISSIONS.tenantSyncConflictResolve);
  const [view, setView] = useState<View>('open');
  const [status, setStatus] = useState('');
  const [resolving, setResolving] = useState<SyncConflictDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<SyncConflictDto>>(
    (query, signal) => accountabilityService.syncConflicts(query, signal),
    [],
  );
  const columns: DataColumn<SyncConflictDto>[] = [
    { id: 'received', header: 'Received', render: (c) => formatInstantIn(c.received_at, timeZone) },
    { id: 'op', header: 'Operation', render: (c) => humanize(c.op_type) },
    { id: 'status', header: 'Status', render: statusChip },
    { id: 'why', header: 'Why not applied', render: (c) => c.error_message ?? c.error_code ?? '—' },
    { id: 'by', header: 'Submitted by', render: submitter },
    { id: 'outcome', header: 'Outcome', render: outcomeText },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (c) => (
        <RowActionsMenu
          label={`operation ${humanize(c.op_type)}`}
          actions={[
            {
              key: 'view',
              label: 'View details',
              onClick: () => {
                void navigate(syncConflictDetailPath(c.operation_id));
              },
            },
            {
              key: 'resolve',
              label: c.submitted_by === me ? 'Resolve (not allowed: you submitted it)' : 'Resolve',
              hidden: !canResolve || c.resolution !== null,
              disabled: c.submitted_by === me,
              onClick: () => {
                setResolving(c);
              },
            },
          ]}
        />
      ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Sync conflicts"
        subtitle="Field operations recorded offline that the server did not apply, with what the device sent"
      />
      <Paper variant="outlined" className="p-3">
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(c) => c.operation_id}
          searchPlaceholder="Search operation or reason"
          reloadKey={reloadKey}
          filters={{
            resolved: view === 'all' ? undefined : view === 'resolved' ? 'true' : 'false',
            status: status || undefined,
          }}
          emptyTitle={view === 'open' ? 'Nothing awaiting review' : 'No operations'}
          onRowClick={(c) => {
            void navigate(syncConflictDetailPath(c.operation_id));
          }}
          toolbar={
            <Box className="flex flex-wrap items-center gap-3">
              <ToggleButtonGroup
                exclusive
                size="small"
                value={view}
                aria-label="Review state"
                onChange={(_e, v: View | null) => {
                  if (v !== null) setView(v);
                }}
              >
                <ToggleButton value="open">Awaiting review</ToggleButton>
                <ToggleButton value="resolved">Resolved</ToggleButton>
                <ToggleButton value="all">All</ToggleButton>
              </ToggleButtonGroup>
              <StaticSelectFilter
                label="Status"
                value={status}
                options={STATUS_OPTIONS}
                onChange={setStatus}
              />
            </Box>
          }
        />
      </Paper>
      {resolving !== null && (
        <ResolveDialog
          conflict={resolving}
          onDone={() => {
            notify.success('Outcome recorded.');
            setReloadKey((k) => k + 1);
          }}
          onClose={() => {
            setResolving(null);
          }}
        />
      )}
    </>
  );
}

function Json({ label, value }: { label: string; value: Record<string, unknown> }) {
  return (
    <Box>
      <Typography variant="subtitle2" component="h3">
        {label}
      </Typography>
      <Box
        component="pre"
        aria-label={label}
        sx={{ m: 0, p: 1.5, bgcolor: 'action.hover', borderRadius: 1, overflowX: 'auto' }}
      >
        {JSON.stringify(value, null, 2)}
      </Box>
    </Box>
  );
}

/** One conflicted / rejected operation: evidence (device payload), server state and the outcome. */
export function SyncConflictDetailPage() {
  const { operationId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const me = useMyUserId();
  const canResolve = useCanMutate(PERMISSIONS.tenantSyncConflictResolve);
  const [resolving, setResolving] = useState(false);
  const load = useCallback(
    (signal: AbortSignal) => accountabilityService.syncConflict(operationId, signal),
    [operationId],
  );
  const res = useAsyncResource(load);
  const c = res.data;
  const mine = c !== null && c.submitted_by === me;
  return (
    <>
      <PageHeader
        title={c === null ? 'Offline operation' : humanize(c.op_type)}
        actions={
          <Box className="flex gap-2">
            <Button component={RouterLink} to={ROUTES.tenantSyncConflicts} variant="outlined">
              All sync conflicts
            </Button>
            {c !== null && c.resolution === null && canResolve && (
              <Button
                variant="contained"
                disabled={mine}
                onClick={() => {
                  setResolving(true);
                }}
              >
                Resolve
              </Button>
            )}
          </Box>
        }
      />
      <AsyncContent resource={res} errorTitle="Could not load the operation">
        {(d) => (
          <Paper variant="outlined" className="flex flex-col gap-3 p-4">
            <Box className="flex items-center gap-2">
              {statusChip(d)}
              <Typography variant="body2">{outcomeText(d)}</Typography>
            </Box>
            {mine && d.resolution === null && (
              <Alert severity="info">Someone else must resolve an operation you submitted.</Alert>
            )}
            <KeyValueGrid
              columns={3}
              items={[
                { label: 'Operation', value: humanize(d.op_type) },
                { label: 'Why not applied', value: d.error_message ?? '—' },
                { label: 'Code', value: d.error_code ?? '—' },
                { label: 'Submitted by', value: submitter(d) },
                {
                  label: 'Recorded on device',
                  value: formatInstantIn(d.created_at_device, timeZone),
                },
                { label: 'Received', value: formatInstantIn(d.received_at, timeZone) },
                { label: 'Device', value: `${d.device_platform} · ${d.device_id}` },
                { label: 'Attempts', value: String(d.attempts) },
              ]}
            />
            {d.resolution !== null && (
              <KeyValueGrid
                columns={3}
                items={[
                  { label: 'Outcome', value: OUTCOME_LABELS[d.resolution.outcome] },
                  { label: 'Reason', value: d.resolution.reason },
                  {
                    label: 'Resolved by',
                    value: (
                      <PersonName
                        userId={d.resolution.resolved_by}
                        name={d.resolution.resolved_by_name}
                      />
                    ),
                  },
                  {
                    label: 'Resolved at',
                    value: formatInstantIn(d.resolution.resolved_at, timeZone),
                  },
                  {
                    label: 'Re-captured as',
                    value:
                      d.resolution.recaptured_entity_id === null
                        ? '—'
                        : `${d.resolution.recaptured_entity_type ?? ''} ${d.resolution.recaptured_entity_id}`,
                  },
                ]}
              />
            )}
            <Json label="What the device sent (evidence)" value={d.payload} />
            <Json label="Server state at the time" value={d.server_state} />
          </Paper>
        )}
      </AsyncContent>
      {resolving && c !== null && (
        <ResolveDialog
          conflict={c}
          onDone={() => {
            notify.success('Outcome recorded.');
            res.reload();
          }}
          onClose={() => {
            setResolving(false);
          }}
        />
      )}
    </>
  );
}
