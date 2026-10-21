import { Alert, Stack } from '@mui/material';
import { formatInstantIn } from '../../utils/time';
import { KeyValueGrid } from '../display/KeyValueGrid';
import { StatusChip } from '../display/StatusChip';
import { isOutsideTolerance, readTrackerComparison } from './trackerComparisonView';

export const NOT_COMPARED_TEXT = 'No tracker position within comparison window';

interface TrackerComparisonProps {
  comparison: Record<string, unknown> | null;
  timeZone: string;
}

const metres = (v: number | null) => (v === null ? '—' : `${String(v)} m`);

/** Phone fix vs machine tracker position at the same observation time. */
export function TrackerComparison({ comparison, timeZone }: TrackerComparisonProps) {
  const view = readTrackerComparison(comparison);
  if (view.kind === 'absent') {
    return <Alert severity="info">No tracker comparison was recorded for this reading.</Alert>;
  }
  if (view.kind === 'not_compared') {
    const phoneMissing = view.reason !== null && view.reason.includes('phone');
    return (
      <Alert severity="info">
        {phoneMissing ? 'Not compared: the phone had no GPS fix.' : NOT_COMPARED_TEXT}
        {view.reason !== null && !phoneMissing && ` (${view.reason})`}
      </Alert>
    );
  }
  const outside = isOutsideTolerance(view);
  return (
    <Stack spacing={1}>
      <div>
        {outside === null ? null : outside ? (
          <StatusChip
            status="OUTSIDE"
            tones={{ OUTSIDE: 'warning' }}
            label="Outside allowed distance — requires review"
          />
        ) : (
          <StatusChip
            status="WITHIN"
            tones={{ WITHIN: 'success' }}
            label="Within allowed distance"
          />
        )}
      </div>
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Distance phone ↔ tracker', value: metres(view.distanceM) },
          { label: 'Allowed distance', value: metres(view.allowedM) },
          {
            label: 'Tracker position time',
            value: formatInstantIn(view.trackerTime, timeZone, true),
          },
          {
            label: 'Time offset',
            value: view.timeOffsetS === null ? '—' : `${String(view.timeOffsetS)} s`,
          },
        ]}
      />
    </Stack>
  );
}
