import { Alert, Box, Button, Paper, TextField, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { toApiError } from '../../api/ApiError';
import { AsyncContent } from '../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../hooks/useAsyncResource';
import { useIdempotencyKey } from '../../hooks/useIdempotencyKey';
import { useNotificationCenter } from '../../notifications/center/NotificationCenterContext';
import { useNotify } from '../../notifications/useNotify';

const MSISDN_HINT =
  'International format, e.g. +255 712 345 678. Leave empty to receive no SMS notifications.';

/** The mobile number SMS notifications go to (normalised by the server). */
export function SmsProfileSection() {
  const { service } = useNotificationCenter();
  const notify = useNotify();
  const load = useCallback((signal: AbortSignal) => service.getProfile(signal), [service]);
  const profile = useAsyncResource(load);
  const [edited, setEdited] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const keyFor = useIdempotencyKey();

  return (
    <Paper variant="outlined" component="section" aria-label="SMS number" className="p-4">
      <Typography variant="subtitle1" component="h2" className="mb-2">
        SMS number
      </Typography>
      <AsyncContent resource={profile} errorTitle="Could not load your SMS number">
        {(p) => {
          const value = edited ?? p.msisdn ?? '';
          const save = () => {
            const body = { msisdn: value.trim() === '' ? null : value.trim() };
            setSaving(true);
            setError(null);
            service
              .updateProfile(body, keyFor(body))
              .then((saved) => {
                notify.success(
                  saved.msisdn === null
                    ? 'SMS number removed.'
                    : `SMS number saved: ${saved.msisdn}.`,
                );
                setEdited(null);
                profile.reload();
              })
              .catch((err: unknown) => {
                const e = toApiError(err);
                setError(e.code === 'INVALID_MSISDN' ? `${e.message} (${e.code})` : e.message);
              })
              .finally(() => {
                setSaving(false);
              });
          };
          return (
            <Box className="flex flex-wrap items-start gap-3">
              <TextField
                size="small"
                label="Mobile number"
                value={value}
                onChange={(e) => {
                  setEdited(e.target.value);
                }}
                helperText={MSISDN_HINT}
                error={error !== null}
                slotProps={{ htmlInput: { inputMode: 'tel', maxLength: 32 } }}
                sx={{ minWidth: 280 }}
              />
              <Button
                variant="outlined"
                onClick={save}
                loading={saving}
                disabled={edited === null || value === (p.msisdn ?? '')}
              >
                Save number
              </Button>
              {error !== null && (
                <Alert severity="error" className="w-full">
                  {error}
                </Alert>
              )}
            </Box>
          );
        }}
      </AsyncContent>
    </Paper>
  );
}
