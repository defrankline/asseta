import { Box, Tooltip } from '@mui/material';
import { useRealtimeStatus } from './hooks';
import type { ConnectionStatus } from './protocol';

type Shown = Exclude<ConnectionStatus, 'idle'>;

const LABELS: Readonly<Record<Shown, string>> = {
  connected: 'Live updates on',
  connecting: 'Connecting live updates…',
  reconnecting: 'Reconnecting live updates…',
  offline: 'Offline: live updates paused',
  denied: 'Live updates unavailable in this console',
};

const COLOURS: Readonly<Record<Shown, string>> = {
  connected: 'success.light',
  connecting: 'warning.light',
  reconnecting: 'warning.light',
  offline: 'grey.500',
  denied: 'error.light',
};

/** Subtle header dot for the realtime link; the tooltip / accessible name says what it means. */
export function ConnectionIndicator() {
  const status = useRealtimeStatus();
  if (status === 'idle') return null;
  const label = LABELS[status];
  const pulsing = status === 'connecting' || status === 'reconnecting';
  return (
    <Tooltip title={label}>
      <Box
        role="status"
        aria-label={label}
        data-status={status}
        className="flex h-6 w-6 items-center justify-center"
      >
        <Box
          component="span"
          sx={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            bgcolor: COLOURS[status],
            border: status === 'offline' || status === 'denied' ? '1px solid' : 'none',
            borderColor: 'common.white',
            '@keyframes asseta-pulse': { '50%': { opacity: 0.35 } },
            animation: pulsing ? 'asseta-pulse 1.2s ease-in-out infinite' : 'none',
            '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
          }}
        />
      </Box>
    </Tooltip>
  );
}
