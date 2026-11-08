import { Alert, Box, Typography } from '@mui/material';
import { useEffect, useState } from 'react';
import type { AdjustmentPreviewDto, AdjustmentPreviewIn } from '../../../../api/adjustmentTypes';
import { adjustmentService } from '../../../../api/services/adjustmentService';
import { RequestEffects } from './adjustmentRecord';

/** The answer to one request body (`for` is that body, so a stale answer is never shown). */
type ForecastAnswer =
  { for: string; kind: 'ready'; preview: AdjustmentPreviewDto } | { for: string; kind: 'failed' };

/** How long the form must be still before asking the server (each keystroke would otherwise call it). */
const FORECAST_DEBOUNCE_MS = 400;

/** What the request will do, the same forecast the decider sees; nothing changes until it is proposed. */
export function AdjustmentForecast({ body }: { body: AdjustmentPreviewIn | null }) {
  const [answer, setAnswer] = useState<ForecastAnswer | null>(null);
  const key = body === null ? null : JSON.stringify(body);
  useEffect(() => {
    if (key === null) return undefined;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      adjustmentService
        .preview(JSON.parse(key) as AdjustmentPreviewIn, controller.signal)
        .then((preview) => {
          if (!controller.signal.aborted) setAnswer({ for: key, kind: 'ready', preview });
        })
        .catch(() => {
          if (!controller.signal.aborted) setAnswer({ for: key, kind: 'failed' });
        });
    }, FORECAST_DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [key]);
  if (key === null) return null;
  const current = answer?.for === key ? answer : null;
  return (
    <Box className="flex flex-col gap-2" aria-label="Forecast">
      <Typography variant="subtitle2">If approved</Typography>
      {current === null && (
        <Typography variant="body2" color="text.secondary">
          Working out the forecast…
        </Typography>
      )}
      {current?.kind === 'failed' && (
        <Alert severity="info">
          The forecast is not available right now; you can still propose this.
        </Alert>
      )}
      {current?.kind === 'ready' && <RequestEffects request={current.preview} />}
    </Box>
  );
}
