import Refresh from '@mui/icons-material/Refresh';
import { Alert, Box, Button, LinearProgress, Paper, Stack, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { newUuid } from '../../../api/ids';
import { withErrorCode } from '../../../api/lifecycle';
import {
  setupChecklistService,
  type SetupChecklistDto,
  type SetupStepDto,
} from '../../../api/services/setupChecklistService';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { LifecycleActionDialog } from '../../../components/lifecycle/LifecycleActionDialog';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { SETUP_ERROR_HINTS, splitSteps } from './setupDisplay';
import { SetupStepCard, type StepActions } from './SetupStepCard';

type Dialog = { kind: 'not-needed'; step: SetupStepDto } | { kind: 'controls' } | null;

export function SetupProgress({ data }: { data: SetupChecklistDto }) {
  const label = `${String(data.steps_done)} of ${String(data.steps_total)} done`;
  return (
    <Paper variant="outlined" className="p-4">
      <Box className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <Typography variant="h6" component="p">
          {label}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {data.percent}%
        </Typography>
      </Box>
      <LinearProgress
        variant="determinate"
        value={data.percent}
        aria-label={`Go-live progress: ${label}`}
        sx={{ height: 8, borderRadius: 4 }}
      />
      {data.complete && (
        <Alert severity="success" className="mt-3">
          Everything is in place. You are ready to go live.
        </Alert>
      )}
    </Paper>
  );
}

/**
 * Go-live checklist (`GET /tenant/setup-checklist`): the ordered steps computed live from the
 * company's data, each linking to the screen that completes it. Owners with `tenant.setup.manage`
 * mark steps as not needed, confirm the default controls and hide the dashboard banner.
 */
export function SetupChecklistPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const { hasPermission, reload: reloadMe } = useSession();
  const canManage = useCanMutate(PERMISSIONS.tenantSetupManage);
  const load = useCallback((signal: AbortSignal) => setupChecklistService.get(signal), []);
  const resource = useAsyncResource(load);
  /** The checklist a write returned (fresher than the last read until the next reload). */
  const [latest, setLatest] = useState<SetupChecklistDto | null>(null);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [busy, setBusy] = useState(false);
  const data = latest ?? resource.data;

  const applied = (result: SetupChecklistDto) => {
    setLatest(result);
    // The dashboard banner reads its figures from /me.
    reloadMe();
  };
  const run = (action: () => Promise<SetupChecklistDto>, done: string) => {
    setBusy(true);
    action().then(
      (result) => {
        applied(result);
        notify.success(done);
        setBusy(false);
      },
      (err: unknown) => {
        notify.error(withErrorCode(err, SETUP_ERROR_HINTS));
        setBusy(false);
      },
    );
  };
  const refresh = () => {
    setLatest(null);
    resource.reload();
  };

  const actions: StepActions = {
    canManage,
    has: (p) => hasPermission(p),
    busy,
    onMarkNotNeeded: (step) => {
      setDialog({ kind: 'not-needed', step });
    },
    onUndoNotNeeded: (step) => {
      run(
        () => setupChecklistService.undoNotNeeded(step.key, newUuid()),
        `${step.title} counts again.`,
      );
    },
    onConfirmControls: () => {
      setDialog({ kind: 'controls' });
    },
  };

  return (
    <>
      <PageHeader
        title="Go-live checklist"
        subtitle="The steps to get your company ready to work live. Each one opens the screen that completes it."
        actions={
          <>
            {canManage && data !== null && (
              <Button
                variant="outlined"
                disabled={busy}
                onClick={() => {
                  if (data.dismissed) {
                    run(
                      () => setupChecklistService.undismiss(newUuid()),
                      'The checklist banner shows on the dashboard again.',
                    );
                  } else {
                    run(
                      () => setupChecklistService.dismiss(newUuid()),
                      'The checklist banner is hidden. This page stays available.',
                    );
                  }
                }}
              >
                {data.dismissed ? 'Show banner again' : 'Hide checklist banner'}
              </Button>
            )}
            <Button
              startIcon={<Refresh />}
              variant="outlined"
              onClick={refresh}
              loading={resource.loading && data !== null}
            >
              Refresh
            </Button>
          </>
        }
      />
      <AsyncContent
        resource={{ ...resource, data }}
        errorTitle="Could not load the go-live checklist"
        loadingLabel="Loading the go-live checklist"
      >
        {(d) => {
          const { shown, unused } = splitSteps(d.steps);
          return (
            <Stack spacing={2}>
              <SetupProgress data={d} />
              {shown.map((step, i) => (
                <SetupStepCard
                  key={step.key}
                  step={step}
                  number={i + 1}
                  timeZone={timeZone}
                  actions={actions}
                  controlsConfirmedBy={
                    step.key === 'CONTROLS_CHOSEN'
                      ? {
                          id: d.controls_confirmed_by ?? null,
                          name: d.controls_confirmed_by_name ?? null,
                          at: d.controls_confirmed_at ?? null,
                        }
                      : undefined
                  }
                />
              ))}
              {unused.length > 0 && (
                <Typography variant="caption" color="text.secondary">
                  Not used by your company, so left out: {unused.map((s) => s.title).join(', ')}.
                </Typography>
              )}
            </Stack>
          );
        }}
      </AsyncContent>
      {dialog?.kind === 'not-needed' && (
        <LifecycleActionDialog<SetupChecklistDto>
          title={`Mark "${dialog.step.title}" as not needed`}
          description="The step counts as done and you can undo this at any time. Say why it does not apply to your business."
          confirmLabel="Mark as not needed"
          reasonLabel="Why it is not needed"
          errorHints={SETUP_ERROR_HINTS}
          onConfirm={(reason, key) =>
            setupChecklistService.markNotNeeded(dialog.step.key, reason, key)
          }
          onDone={(result) => {
            applied(result);
            notify.success(`${dialog.step.title} marked as not needed.`);
          }}
          onClose={() => {
            setDialog(null);
          }}
        />
      )}
      {dialog?.kind === 'controls' && (
        <LifecycleActionDialog<SetupChecklistDto>
          title="Keep the default controls"
          description="The platform's default controls (approvals, limits and checks) stay as they are. You can change any of them later under Policies."
          confirmLabel="Our default controls are fine"
          reason="optional"
          reasonLabel="Note"
          errorHints={SETUP_ERROR_HINTS}
          onConfirm={(note, key) => setupChecklistService.confirmControls(note || null, key)}
          onDone={(result) => {
            applied(result);
            notify.success('Default controls confirmed.');
          }}
          onClose={() => {
            setDialog(null);
          }}
        />
      )}
    </>
  );
}
