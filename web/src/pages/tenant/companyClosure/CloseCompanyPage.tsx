import { Alert, Button, Link, Paper, Stack, TextField, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import type { ApiError } from '../../../api/ApiError';
import { REASON_MAX, REASON_MIN, withPlainHint } from '../../../api/lifecycle';
import {
  companyClosureService,
  type CompanyDeletionRequestDto,
  type CompanyDeletionStatusDto,
} from '../../../api/services/companyClosureService';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { ConfirmDialog } from '../../../components/forms/ConfirmDialog';
import { LifecycleActionDialog } from '../../../components/lifecycle/LifecycleActionDialog';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useNow } from '../../../hooks/useNow';
import { ROUTES } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatDateIn, formatInstantIn } from '../../../utils/time';
import {
  CANCEL_ERROR_HINTS,
  CLOSE_ERROR_HINTS,
  daysLeft,
  daysLeftText,
  DELETION_STATUS_LABELS,
  DELETION_STATUS_TONES,
  nameMatches,
} from './closureDisplay';

function RequestForm({
  status,
  onRequested,
}: {
  status: CompanyDeletionStatusDto;
  onRequested: () => void;
}) {
  const notify = useNotify();
  const keyFor = useIdempotencyKey();
  const [confirmName, setConfirmName] = useState('');
  const [reason, setReason] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const trimmedReason = reason.trim();
  const reasonOk = trimmedReason.length >= REASON_MIN && trimmedReason.length <= REASON_MAX;
  const matches = nameMatches(confirmName, status.company_name);
  const days = String(status.waiting_days);

  const submit = async () => {
    const body = { confirm_name: confirmName.trim(), reason: trimmedReason };
    try {
      await companyClosureService.request(body, keyFor(body));
      notify.success('Closure requested. The company is now read-only.');
      onRequested();
    } catch (e) {
      setError(withPlainHint(e, CLOSE_ERROR_HINTS));
    }
  };

  return (
    <Stack spacing={3}>
      <Alert severity="warning">
        All of {status.company_name} will be deleted {days} days after you confirm. The company
        becomes read-only immediately. Any owner can cancel during those days. Download your data
        export first:{' '}
        <Link component={RouterLink} to={ROUTES.tenantDataExport}>
          Data export
        </Link>
        .
      </Alert>
      {status.request?.status === 'CANCELLED' && (
        <Typography variant="body2" color="text.secondary">
          The last closure request was cancelled
          {status.request.cancelled_by_name !== null
            ? ` by ${status.request.cancelled_by_name}`
            : ''}
          .
        </Typography>
      )}
      <Paper variant="outlined" className="p-4">
        <Stack spacing={2}>
          <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 600 }}>
            Close {status.company_name}
          </Typography>
          <TextField
            label="Type the company name to confirm"
            value={confirmName}
            onChange={(e) => {
              setConfirmName(e.target.value);
              setError(null);
            }}
            helperText={`Type "${status.company_name}"`}
            autoComplete="off"
            required
            fullWidth
          />
          <TextField
            label="Reason"
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
              setError(null);
            }}
            helperText={`At least ${String(REASON_MIN)} characters. Recorded with the request.`}
            multiline
            minRows={2}
            required
            fullWidth
          />
          {error !== null && (
            <Alert severity="error" role="alert">
              {error.message}
            </Alert>
          )}
          <div>
            <Button
              variant="contained"
              color="error"
              disabled={!matches || !reasonOk}
              onClick={() => {
                setConfirming(true);
              }}
            >
              Close company
            </Button>
          </div>
        </Stack>
      </Paper>
      {confirming && (
        <ConfirmDialog
          open
          destructive
          title={`Close ${status.company_name}?`}
          message={`The company becomes read-only now. All of its data is deleted in ${days} days unless an owner cancels before then.`}
          confirmLabel="Close company"
          onConfirm={submit}
          onClose={() => {
            setConfirming(false);
          }}
        />
      )}
    </Stack>
  );
}

function RequestDetails({
  request,
  onCancelled,
}: {
  request: CompanyDeletionRequestDto;
  onCancelled: () => void;
}) {
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const now = useNow(60_000);
  const [cancelling, setCancelling] = useState(false);
  const left = daysLeft(request.scheduled_for, now);
  const requestedBy = request.requested_by_name ?? 'Unknown';

  return (
    <Stack spacing={3}>
      {request.status === 'REQUESTED' && (
        <Alert severity="warning">
          This company is read-only. All of its data will be deleted on{' '}
          {formatDateIn(request.scheduled_for, timeZone)} ({daysLeftText(left)}). Any owner can
          cancel until then.
        </Alert>
      )}
      {request.status === 'IN_PROGRESS' && (
        <Alert severity="info">
          The deletion has started and can no longer be cancelled. The company&apos;s data is being
          removed.
        </Alert>
      )}
      {request.status === 'COMPLETED' && (
        <Alert severity="info">
          The company&apos;s data was deleted
          {request.completed_at !== null
            ? ` on ${formatDateIn(request.completed_at, timeZone)}`
            : ''}
          .
        </Alert>
      )}
      <Paper variant="outlined" className="p-4">
        <Stack spacing={2}>
          <div>
            <StatusChip
              status={request.status}
              tones={DELETION_STATUS_TONES}
              label={DELETION_STATUS_LABELS[request.status]}
            />
          </div>
          <KeyValueGrid
            items={[
              { label: 'Requested by', value: requestedBy },
              { label: 'Requested', value: formatInstantIn(request.requested_at, timeZone) },
              {
                label: 'Deletion date',
                value:
                  request.status === 'REQUESTED'
                    ? `${formatDateIn(request.scheduled_for, timeZone)} (${daysLeftText(left)})`
                    : formatDateIn(request.scheduled_for, timeZone),
              },
              { label: 'Reason', value: request.reason },
              { label: 'Waiting period', value: `${String(request.waiting_days)} days` },
            ]}
          />
          {request.status === 'REQUESTED' && (
            <div>
              <Button
                variant="outlined"
                onClick={() => {
                  setCancelling(true);
                }}
              >
                Cancel closure
              </Button>
            </div>
          )}
        </Stack>
      </Paper>
      {cancelling && (
        <LifecycleActionDialog<CompanyDeletionRequestDto>
          title="Cancel closure"
          description="The closure request is withdrawn and normal access is restored. Nothing is deleted."
          confirmLabel="Cancel closure"
          reasonHelp="Recorded with the request."
          errorHints={CANCEL_ERROR_HINTS}
          onConfirm={(reason, key) => companyClosureService.cancel(reason, key)}
          onDone={() => {
            notify.success('Closure cancelled. Normal access is restored.');
            onCancelled();
          }}
          onClose={() => {
            setCancelling(false);
          }}
        />
      )}
    </Stack>
  );
}

/**
 * Administration -> Close company (`tenant.company.close`). Requesting turns the company read-only at
 * once and deletes all of its data after the platform-wide waiting period; any holder of the
 * permission can cancel until the deletion starts. Both stay open while the company is read-only.
 */
export function CloseCompanyPage() {
  const { mode, reload: reloadSession } = useSession();
  const tenantKey = mode.kind === 'tenant' ? mode.tenantId : '';
  const load = useCallback((signal: AbortSignal) => companyClosureService.getStatus(signal), []);
  const res = useAsyncResource(load, [tenantKey]);
  const changed = () => {
    res.reload();
    reloadSession();
  };

  return (
    <>
      <PageHeader
        title="Close company"
        subtitle="Close the company and delete all of its data after a waiting period"
      />
      <AsyncContent resource={res} errorTitle="Could not load the closure status">
        {(status) => {
          const request = status.request;
          if (request === null || request.status === 'CANCELLED') {
            return <RequestForm status={status} onRequested={changed} />;
          }
          return <RequestDetails request={request} onCancelled={changed} />;
        }}
      </AsyncContent>
    </>
  );
}
