import { Box, Paper, Typography } from '@mui/material';
import { useCallback } from 'react';
import { tenantMlService } from '../../../api/services/insightsService';
import type { MlReadinessDto, TenantMlStatusDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { formatInstantIn } from '../../../utils/time';
import { factText, ML_STATE_LABELS, ML_STATE_TONES, readinessLabel } from './insightsDisplay';

/** Each minimum next to what this tenant has so far (both are plain facts, no score). */
function Minimums({ readiness }: { readiness: MlReadinessDto }) {
  const items = Object.entries(readiness.minimums).map(([key, min]) => {
    const observedKey = key.replace(/^min_/, '');
    const observed = readiness.observed[observedKey] ?? readiness.observed[key];
    return {
      label: readinessLabel(key),
      value:
        observed === undefined
          ? `needs ${factText(min)}`
          : `${factText(observed)} of ${factText(min)} needed`,
    };
  });
  if (items.length === 0) return null;
  return <KeyValueGrid columns={3} items={items} />;
}

function StatusBody({ status, timeZone }: { status: TenantMlStatusDto; timeZone: string }) {
  const readiness = status.readiness;
  const short = ML_STATE_LABELS[status.state];
  return (
    <Box className="flex flex-col gap-2">
      <Box className="flex flex-wrap items-center gap-2">
        <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 600 }}>
          Anomaly model
        </Typography>
        <StatusChip status={status.state} tones={ML_STATE_TONES} label={short} />
      </Box>
      {status.label !== short && <Typography variant="body2">{status.label}</Typography>}
      <Typography variant="body2" color="text.secondary">
        {status.summary}
      </Typography>
      {status.deployed !== null && (
        <Typography variant="body2" color="text.secondary">
          Version {status.deployed.version},{' '}
          {status.deployed.mode === 'ACTIVE' ? 'active' : 'shadow (observed only)'} since{' '}
          {formatInstantIn(status.deployed.deployed_at, timeZone)}.
        </Typography>
      )}
      {status.state === 'NOT_ENOUGH_HISTORY' && readiness !== null && (
        <Box className="flex flex-col gap-2">
          {readiness.reasons.length > 0 && (
            <Box component="ul" className="m-0 pl-5" aria-label="What is missing">
              {readiness.reasons.map((r) => (
                <li key={r}>
                  <Typography variant="body2">{r}</Typography>
                </li>
              ))}
            </Box>
          )}
          <Minimums readiness={readiness} />
          <Typography variant="caption" color="text.secondary">
            Last assessed {formatInstantIn(readiness.computed_at, timeZone)}. Deterministic checks
            keep working meanwhile.
          </Typography>
        </Box>
      )}
    </Box>
  );
}

/** Plain-language model status for the tenant (`GET /tenant/ml/status`): state and reasons only. */
export function MlStatusCard({ timeZone }: { timeZone: string }) {
  const load = useCallback((signal: AbortSignal) => tenantMlService.status(signal), []);
  const res = useAsyncResource(load);
  return (
    <Paper variant="outlined" component="section" aria-label="Model status" className="p-4">
      <AsyncContent
        resource={res}
        errorTitle="Could not load the model status"
        loadingLabel="Loading model status"
      >
        {(status) => <StatusBody status={status} timeZone={timeZone} />}
      </AsyncContent>
    </Paper>
  );
}
