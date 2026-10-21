import { Alert, Stack, Typography } from '@mui/material';
import type { EffectivePolicyDto } from '../../../api/types';
import type { AsyncResource } from '../../../hooks/useAsyncResource';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { LoadingState } from '../../../components/feedback/LoadingState';
import { humanize } from '../../../utils/text';
import type { CapturePolicyView } from './capturePolicy';

interface CapturePolicySummaryProps {
  /** null when the user may not read policies. */
  resource: AsyncResource<EffectivePolicyDto> | null;
  view: CapturePolicyView | null;
  kindLabel: string;
}

/** The effective METER_CAPTURE policy that applies to this reading, shown before submitting. */
export function CapturePolicySummary({ resource, view, kindLabel }: CapturePolicySummaryProps) {
  if (resource === null) {
    return (
      <Alert severity="info">
        The server applies the effective meter-capture policy to this reading (viewing it needs the
        policy read permission).
      </Alert>
    );
  }
  if (resource.error !== null) {
    return (
      <Alert severity="warning">
        Could not load the effective policy ({resource.error.message}). The server still applies it.
      </Alert>
    );
  }
  if (resource.data === null || view === null) return <LoadingState label="Loading policy" />;
  return (
    <Stack spacing={1}>
      <Typography variant="subtitle2" component="h3">
        Effective meter-capture policy · {resource.data.version_stamp}
      </Typography>
      <KeyValueGrid
        columns={3}
        items={[
          {
            label: `Required mode (${kindLabel})`,
            value: view.requiredMode === null ? '—' : humanize(view.requiredMode),
          },
          {
            label: 'Photo for manual readings',
            value:
              view.manualPhotoRequired === null
                ? '—'
                : view.manualPhotoRequired
                  ? 'Required'
                  : 'Optional',
          },
          {
            label: 'Without valid GPS',
            value:
              view.gpsEnforcement === 'HARD'
                ? 'Reading rejected'
                : view.gpsEnforcement === 'SOFT'
                  ? 'Kept as provisional for review'
                  : '—',
          },
          {
            label: 'GPS max accuracy',
            value: view.gpsMaxAccuracyM === null ? '—' : `${String(view.gpsMaxAccuracyM)} m`,
          },
          {
            label: 'GPS max fix age',
            value: view.gpsMaxAgeSeconds === null ? '—' : `${String(view.gpsMaxAgeSeconds)} s`,
          },
        ]}
      />
    </Stack>
  );
}
