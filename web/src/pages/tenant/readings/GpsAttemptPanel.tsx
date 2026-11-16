import { Alert, Box, Button, Stack, Typography } from '@mui/material';
import type { GpsIn } from '../../../api/types';
import { GPS_STATUS_LABELS } from '../../../components/meter/gps';
import { LoadingState } from '../../../components/feedback/LoadingState';

interface GpsAttemptPanelProps {
  /** null while the browser is attempting a fix. */
  gps: GpsIn | null;
  onRetry: () => void;
}

/** Shows the real outcome of this browser's GPS attempt; failures carry no coordinates. */
export function GpsAttemptPanel({ gps, onRetry }: GpsAttemptPanelProps) {
  if (gps === null) return <LoadingState label="Attempting a GPS fix with this browser…" />;
  const fix = gps.status === 'FIX';
  return (
    <Stack spacing={1}>
      <Alert
        severity={fix ? 'success' : 'warning'}
        action={
          <Button color="inherit" size="small" onClick={onRetry}>
            Try GPS again
          </Button>
        }
      >
        <Typography variant="body2" component="div">
          GPS result: <strong>{GPS_STATUS_LABELS[gps.status]}</strong>
        </Typography>
        {fix ? (
          <Box component="span" className="font-mono text-xs">
            {String(gps.latitude)}, {String(gps.longitude)} · ±{String(gps.accuracy_m)} m
          </Box>
        ) : (
          <Typography variant="caption" component="div">
            No coordinates will be sent. The reading is submitted with this result and the policy
            decides whether it is kept for review or rejected.
          </Typography>
        )}
      </Alert>
    </Stack>
  );
}
