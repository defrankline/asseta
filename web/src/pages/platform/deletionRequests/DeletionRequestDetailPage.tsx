import CheckCircle from '@mui/icons-material/CheckCircle';
import RadioButtonUnchecked from '@mui/icons-material/RadioButtonUnchecked';
import {
  Alert,
  Button,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import { useCallback, useState } from 'react';
import { useParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import {
  companyClosureService,
  type CompanyDeletionRequestDto,
} from '../../../api/services/companyClosureService';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { EntityDetailsLayout } from '../../../components/lifecycle/EntityDetailsLayout';
import { LifecycleActionDialog } from '../../../components/lifecycle/LifecycleActionDialog';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { ROUTES } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import {
  DELETION_STATUS_LABELS,
  DELETION_STATUS_TONES,
  DELETION_STEPS,
  stepLabel,
} from '../../tenant/companyClosure/closureDisplay';

export const RUN_NOW_WARNING =
  'Only when the company owner asked for immediate deletion in writing.';

const RUN_NOW_HINTS: Readonly<Record<string, string>> = {
  DELETION_NOT_ACTIVE: 'This request was cancelled or has already finished. Reload to see it.',
};

const ACTIVE = new Set(['REQUESTED', 'IN_PROGRESS']);

function StepsSection({ request }: { request: CompanyDeletionRequestDto }) {
  const done = new Set(request.steps_done);
  const known = new Set(DELETION_STEPS.map((s) => s.code));
  const steps = [
    ...DELETION_STEPS.map((s) => s.code),
    ...request.steps_done.filter((s) => !known.has(s)),
  ];
  return (
    <Paper variant="outlined" className="p-4">
      <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 600 }}>
        Steps done
      </Typography>
      <List dense aria-label="Deletion steps">
        {steps.map((code) => (
          <ListItem key={code} disableGutters>
            <ListItemIcon sx={{ minWidth: 32 }}>
              {done.has(code) ? (
                <CheckCircle color="success" fontSize="small" />
              ) : (
                <RadioButtonUnchecked color="disabled" fontSize="small" />
              )}
            </ListItemIcon>
            <ListItemText
              primary={stepLabel(code)}
              secondary={done.has(code) ? 'Done' : 'Not yet'}
            />
          </ListItem>
        ))}
      </List>
    </Paper>
  );
}

/**
 * One company closure request: who asked and when, the deletion date, the steps done, attempts and the
 * last error. "Run now" (`platform.tenant.deletion.execute`) starts the deletion before the waiting
 * period ends.
 */
export function DeletionRequestDetailPage() {
  const { requestId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const { hasPermission } = useSession();
  const canExecute = hasPermission(PERMISSIONS.platformTenantDeletionExecute);
  const [running, setRunning] = useState(false);
  const load = useCallback(
    (signal: AbortSignal) => companyClosureService.get(requestId, signal),
    [requestId],
  );
  const res = useAsyncResource(load);
  const request = res.data;
  const at = (v: string | null) => formatInstantIn(v, timeZone);

  return (
    <>
      <EntityDetailsLayout
        title={request === null ? 'Deletion request' : request.tenant_name}
        subtitle="Company closure request"
        back={{ label: 'All deletion requests', to: ROUTES.platformDeletionRequests }}
        {...(request !== null
          ? {
              status: (
                <StatusChip
                  status={request.status}
                  tones={DELETION_STATUS_TONES}
                  label={DELETION_STATUS_LABELS[request.status]}
                />
              ),
              actions:
                canExecute && ACTIVE.has(request.status) ? (
                  <Button
                    variant="contained"
                    color="error"
                    onClick={() => {
                      setRunning(true);
                    }}
                  >
                    Run now
                  </Button>
                ) : undefined,
            }
          : {})}
      >
        <AsyncContent
          resource={res}
          errorTitle="Could not load the deletion request"
          loadingLabel="Loading deletion request"
        >
          {(r) => (
            <Stack spacing={3}>
              {r.last_error !== null && (
                <Alert severity="error">
                  <strong>Last error:</strong> {r.last_error}
                </Alert>
              )}
              <Paper variant="outlined" className="p-4">
                <KeyValueGrid
                  items={[
                    { label: 'Requested by', value: r.requested_by_name ?? '—' },
                    { label: 'Requested', value: at(r.requested_at) },
                    { label: 'Reason', value: r.reason },
                    { label: 'Deletion date', value: at(r.scheduled_for) },
                    { label: 'Waiting period', value: `${String(r.waiting_days)} days` },
                    { label: 'Attempts', value: String(r.attempts) },
                    { label: 'Started', value: at(r.started_at) },
                    { label: 'Completed', value: at(r.completed_at) },
                    { label: 'Policy version', value: r.policy_version },
                    ...(r.cancelled_at !== null
                      ? [
                          { label: 'Cancelled by', value: r.cancelled_by_name ?? '—' },
                          { label: 'Cancelled', value: at(r.cancelled_at) },
                          { label: 'Cancel reason', value: r.cancel_reason ?? '—' },
                        ]
                      : []),
                    ...(r.execute_now_at !== null
                      ? [
                          { label: 'Run early', value: at(r.execute_now_at) },
                          { label: 'Run early reason', value: r.execute_now_reason ?? '—' },
                        ]
                      : []),
                  ]}
                />
              </Paper>
              <StepsSection request={r} />
            </Stack>
          )}
        </AsyncContent>
      </EntityDetailsLayout>
      {request !== null && running && (
        <LifecycleActionDialog<CompanyDeletionRequestDto>
          title={`Run deletion now: ${request.tenant_name}`}
          description={
            <Stack spacing={1}>
              <Alert severity="warning">{RUN_NOW_WARNING}</Alert>
              <span>
                The deletion starts at the next worker run instead of on the scheduled date. All of
                the company&apos;s data is deleted and this cannot be undone.
              </span>
            </Stack>
          }
          confirmLabel="Run now"
          reasonHelp="Say where the owner's written request is. Recorded in the audit log."
          errorHints={RUN_NOW_HINTS}
          onConfirm={(reason, key) => companyClosureService.executeNow(request.id, reason, key)}
          onDone={() => {
            notify.success('The deletion will start at the next worker run.');
            res.reload();
          }}
          onClose={() => {
            setRunning(false);
          }}
          onReload={res.reload}
        />
      )}
    </>
  );
}
