import { Alert, Box, Paper, Typography } from '@mui/material';

interface HoursComparisonProps {
  /** Closing − opening hour-meter reading (decimal string), null until both exist. */
  meterHours: string | null;
  /** Approved non-billable standby/downtime hours (decimal string). */
  nonbillableHours: string;
  /** Hours billed under the contract rules (decimal string), null until computable. */
  billableHours: string | null;
  /** Contract minimum hours (decimal string). */
  minimumHours?: string;
}

function Tile({ label, value, caption }: { label: string; value: string; caption: string }) {
  return (
    <Paper variant="outlined" className="p-3" role="group" aria-label={label}>
      <Typography variant="caption" color="text.secondary" component="div">
        {label}
      </Typography>
      <Typography variant="h6" component="div" sx={{ fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {caption}
      </Typography>
    </Paper>
  );
}

const hours = (v: string | null) => (v === null ? 'Not yet available' : `${v} h`);

/**
 * Meter (engine) hours and billable hours side by side, never merged: billable hours follow the
 * contract and billing policy, not raw meter movement. Values are shown exactly as the API sent them.
 */
export function HoursComparison({
  meterHours,
  nonbillableHours,
  billableHours,
  minimumHours,
}: HoursComparisonProps) {
  return (
    <Box className="flex flex-col gap-2">
      <Box className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <Tile
          label="Meter hours"
          value={hours(meterHours)}
          caption="Closing − opening hour-meter reading"
        />
        <Tile
          label="Non-billable hours"
          value={`${nonbillableHours} h`}
          caption="Approved standby / downtime periods"
        />
        <Tile
          label="Billable hours"
          value={hours(billableHours)}
          caption={
            minimumHours !== undefined
              ? `After policy rounding; contract minimum ${minimumHours} h`
              : 'After policy rounding and contract minimum'
          }
        />
      </Box>
      <Alert severity="info">
        Engine/meter hours are not billable hours. Billable hours start from the meter hours, remove
        approved non-billable periods, apply the billing rounding policy and then the contract
        minimum.
        {meterHours === null &&
          ' Both opening and closing readings are needed before either is shown.'}
      </Alert>
    </Box>
  );
}
