import { Box, Button, Paper, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { platformMlService } from '../../../api/services/platformMlService';
import type { MlSettingsDto } from '../../../api/types';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { LifecycleActionDialog } from '../../../components/lifecycle/LifecycleActionDialog';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';

export const SWITCH_OFF_EFFECT =
  'All scoring stops on every tenant: no model runs and no new predictions are recorded. Deterministic rules keep working.';
export const SWITCH_ON_EFFECT =
  'Deployed models resume scoring on the next scheduled run. Shadow models stay invisible to tenants.';

function SwitchBody({
  settings,
  timeZone,
  canManage,
  onToggle,
}: {
  settings: MlSettingsDto;
  timeZone: string;
  canManage: boolean;
  onToggle: () => void;
}) {
  const on = settings.inference_enabled;
  return (
    <Box className="flex flex-wrap items-start justify-between gap-3">
      <Box className="flex flex-col gap-1">
        <Box className="flex items-center gap-2">
          <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 600 }}>
            Inference switch
          </Typography>
          <StatusChip
            status={on ? 'ON' : 'OFF'}
            tones={{ ON: 'success', OFF: 'error' }}
            label={on ? 'Inference on' : 'Inference off'}
          />
        </Box>
        <Typography variant="body2" color="text.secondary">
          {on
            ? 'Deployed models may score. Switching off stops all scoring; rules keep working.'
            : 'All scoring is stopped platform-wide; deterministic rules keep working.'}
        </Typography>
        <Typography variant="body2">Reason: {settings.reason}</Typography>
        {settings.updated_at !== null && (
          <Typography variant="caption" color="text.secondary">
            Changed {formatInstantIn(settings.updated_at, timeZone)}
          </Typography>
        )}
      </Box>
      {canManage && (
        <Button variant="outlined" color={on ? 'error' : 'primary'} onClick={onToggle}>
          {on ? 'Switch inference off' : 'Switch inference on'}
        </Button>
      )}
    </Box>
  );
}

/** Platform-wide hard switch for model inference (GET/PUT settings, reason + lock_version). */
export function InferenceSwitchCard({
  timeZone,
  canManage,
}: {
  timeZone: string;
  canManage: boolean;
}) {
  const notify = useNotify();
  const [open, setOpen] = useState(false);
  const load = useCallback((signal: AbortSignal) => platformMlService.getSettings(signal), []);
  const res = useAsyncResource(load);
  const settings = res.data;
  return (
    <Paper variant="outlined" component="section" aria-label="Inference switch" className="p-4">
      <AsyncContent resource={res} errorTitle="Could not load the inference switch">
        {(s) => (
          <SwitchBody
            settings={s}
            timeZone={timeZone}
            canManage={canManage}
            onToggle={() => {
              setOpen(true);
            }}
          />
        )}
      </AsyncContent>
      {open && settings !== null && (
        <LifecycleActionDialog<MlSettingsDto>
          title={settings.inference_enabled ? 'Switch inference off' : 'Switch inference on'}
          description={settings.inference_enabled ? SWITCH_OFF_EFFECT : SWITCH_ON_EFFECT}
          confirmLabel={settings.inference_enabled ? 'Switch off' : 'Switch on'}
          reasonHelp="Recorded in the audit log with your name."
          onConfirm={(reason, key) =>
            platformMlService.updateSettings(
              {
                inference_enabled: !settings.inference_enabled,
                reason,
                lock_version: settings.lock_version,
              },
              key,
            )
          }
          onDone={(next) => {
            notify.success(
              next.inference_enabled ? 'Inference switched on.' : 'Inference switched off.',
            );
            res.reload();
          }}
          onClose={() => {
            setOpen(false);
          }}
          onReload={res.reload}
        />
      )}
    </Paper>
  );
}
