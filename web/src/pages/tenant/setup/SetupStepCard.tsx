import CheckCircle from '@mui/icons-material/CheckCircle';
import RadioButtonUnchecked from '@mui/icons-material/RadioButtonUnchecked';
import { Avatar, Box, Button, Chip, Link, Paper, Stack, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { SetupCheckDto, SetupStepDto } from '../../../api/services/setupChecklistService';
import { StatusChip } from '../../../components/display/StatusChip';
import { formatInstantIn } from '../../../utils/time';
import { PersonName } from '../shared/PersonName';
import {
  checkCount,
  goToLabel,
  screenName,
  STEP_STATUS_LABELS,
  STEP_STATUS_TONES,
  stepCount,
} from './setupDisplay';

export interface StepActions {
  /** The user may record the owner's choices (`tenant.setup.manage`, tenant not read-only). */
  canManage: boolean;
  /** Whether the user holds a permission (to hint when someone else must do a step). */
  has: (permission: string) => boolean;
  busy: boolean;
  onMarkNotNeeded: (step: SetupStepDto) => void;
  onUndoNotNeeded: (step: SetupStepDto) => void;
  onConfirmControls: () => void;
}

function CheckRow({ check }: { check: SetupCheckDto }) {
  const count = checkCount(check);
  const name = screenName(check.link);
  return (
    <Box component="li" className="flex flex-wrap items-center gap-2">
      {check.done ? (
        <CheckCircle fontSize="small" color="success" titleAccess="Part done" />
      ) : (
        <RadioButtonUnchecked fontSize="small" color="action" titleAccess="Part still to do" />
      )}
      <Typography variant="body2">{check.label}</Typography>
      {check.optional && <Chip size="small" variant="outlined" label="Optional" />}
      {count !== null && (
        <Typography variant="caption" color="text.secondary">
          {count}
        </Typography>
      )}
      {!check.done && (
        <Link component={RouterLink} to={check.link} variant="body2">
          {name === null ? 'Open' : `Open ${name}`}
        </Link>
      )}
    </Box>
  );
}

/** One go-live step: status, plain-English description, counts, the screen to do it and its parts. */
export function SetupStepCard({
  step,
  number,
  timeZone,
  actions,
  controlsConfirmedBy,
}: {
  step: SetupStepDto;
  number: number;
  timeZone: string;
  actions: StepActions;
  /** For the controls step: who confirmed the default controls, if anyone. */
  controlsConfirmedBy?: { id: string | null; name: string | null; at: string | null } | undefined;
}) {
  const count = stepCount(step);
  const done = step.status === 'DONE';
  const notNeeded = step.status === 'NOT_NEEDED';
  const checks = step.checks ?? [];
  const titleId = `setup-step-${step.key}`;
  return (
    <Paper
      variant="outlined"
      component="section"
      aria-labelledby={titleId}
      className="p-4"
      sx={notNeeded ? { opacity: 0.8 } : undefined}
    >
      <Box className="flex items-start gap-3">
        <Avatar
          aria-hidden
          sx={{ width: 32, height: 32, fontSize: 15, bgcolor: done ? 'success.main' : 'grey.500' }}
        >
          {number}
        </Avatar>
        <Stack spacing={1.5} className="min-w-0 flex-1">
          <Box className="flex flex-wrap items-center gap-2">
            <Typography id={titleId} variant="subtitle1" component="h2" sx={{ fontWeight: 600 }}>
              {step.title}
            </Typography>
            <StatusChip
              status={step.status}
              tones={STEP_STATUS_TONES}
              label={STEP_STATUS_LABELS[step.status]}
            />
            {count !== null && (
              <Typography variant="body2" color="text.secondary">
                {count}
              </Typography>
            )}
          </Box>
          <Typography variant="body2" color="text.secondary">
            {step.description}
          </Typography>
          {checks.length > 0 && (
            <Box component="ul" className="m-0 flex list-none flex-col gap-1 p-0">
              {checks.map((c) => (
                <CheckRow key={c.key} check={c} />
              ))}
            </Box>
          )}
          {notNeeded && step.not_needed != null && (
            <Typography variant="body2">
              Marked as not needed by{' '}
              <PersonName
                userId={step.not_needed.marked_by}
                name={step.not_needed.marked_by_name}
              />{' '}
              on {formatInstantIn(step.not_needed.marked_at, timeZone)}
              {step.not_needed.reason !== null && step.not_needed.reason !== ''
                ? `: ${step.not_needed.reason}`
                : ''}
            </Typography>
          )}
          {controlsConfirmedBy !== undefined && controlsConfirmedBy.at !== null && (
            <Typography variant="body2">
              Default controls confirmed by{' '}
              <PersonName userId={controlsConfirmedBy.id} name={controlsConfirmedBy.name} /> on{' '}
              {formatInstantIn(controlsConfirmedBy.at, timeZone)}
            </Typography>
          )}
          <Box className="flex flex-wrap items-center gap-2">
            {!notNeeded && (
              <Button
                component={RouterLink}
                to={step.link}
                variant={done ? 'outlined' : 'contained'}
                size="small"
              >
                {goToLabel(step.link)}
              </Button>
            )}
            {step.key === 'CONTROLS_CHOSEN' && !done && actions.canManage && (
              <Button
                size="small"
                variant="outlined"
                disabled={actions.busy}
                onClick={actions.onConfirmControls}
              >
                Our default controls are fine
              </Button>
            )}
            {step.can_mark_not_needed && actions.canManage && !done && !notNeeded && (
              <Button
                size="small"
                disabled={actions.busy}
                onClick={() => {
                  actions.onMarkNotNeeded(step);
                }}
              >
                Mark as not needed
              </Button>
            )}
            {notNeeded && actions.canManage && (
              <Button
                size="small"
                disabled={actions.busy}
                onClick={() => {
                  actions.onUndoNotNeeded(step);
                }}
              >
                Undo
              </Button>
            )}
            {!done && !notNeeded && !actions.has(step.required_permission) && (
              <Typography variant="caption" color="text.secondary">
                Someone with access to that screen may need to finish this step.
              </Typography>
            )}
          </Box>
        </Stack>
      </Box>
    </Paper>
  );
}
