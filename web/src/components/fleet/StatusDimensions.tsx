import { Box, Chip, Tooltip, Typography } from '@mui/material';
import type { Compliance, Observed } from '../../api/types';
import { humanize } from '../../utils/text';
import type { StatusTone } from '../display/StatusChip';

interface StatusDimensionsProps {
  reportedWorkStatus: string;
  observedEngine: Observed;
  observedMotion: Observed;
  locationCompliance: Compliance;
}

const TONES: Readonly<Record<string, StatusTone>> = {
  ON: 'success',
  MOVING: 'info',
  OFF: 'default',
  STATIONARY: 'default',
  COMPLIANT: 'success',
  NON_COMPLIANT: 'error',
};

const UNKNOWN_HELP = 'Unknown — insufficient evidence (no verified sensor or fresh position).';

function DimensionValue({ value }: { value: string }) {
  if (value === 'UNKNOWN') {
    return (
      <Tooltip title={UNKNOWN_HELP}>
        <Chip size="small" variant="outlined" label="Unknown" aria-description={UNKNOWN_HELP} />
      </Tooltip>
    );
  }
  const tone = TONES[value] ?? 'default';
  return (
    <Chip
      size="small"
      label={humanize(value)}
      color={tone}
      variant={tone === 'default' ? 'outlined' : 'filled'}
    />
  );
}

/**
 * The four independent machine status dimensions (R1-D). They are never merged into a single
 * "working" status; UNKNOWN is shown explicitly when evidence is insufficient.
 */
export function StatusDimensions({
  reportedWorkStatus,
  observedEngine,
  observedMotion,
  locationCompliance,
}: StatusDimensionsProps) {
  const rows = [
    { label: 'Reported work status', hint: 'From supervisor reports', value: reportedWorkStatus },
    { label: 'Engine (sensor)', hint: 'Verified ignition input only', value: observedEngine },
    { label: 'Motion (sensor)', hint: 'From fresh GPS speed', value: observedMotion },
    { label: 'Location compliance', hint: 'Against geofences', value: locationCompliance },
  ];
  return (
    <Box component="dl" className="m-0 grid grid-cols-2 gap-2" aria-label="Status dimensions">
      {rows.map((r) => (
        <Box key={r.label}>
          <Typography component="dt" variant="caption" color="text.secondary" title={r.hint}>
            {r.label}
          </Typography>
          <Box component="dd" className="m-0">
            <DimensionValue value={r.value} />
          </Box>
        </Box>
      ))}
    </Box>
  );
}
