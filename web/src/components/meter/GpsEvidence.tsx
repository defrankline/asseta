import { Stack } from '@mui/material';
import type { GpsStatus } from '../../api/types';
import { formatInstantIn } from '../../utils/time';
import { KeyValueGrid } from '../display/KeyValueGrid';
import { StatusChip, type StatusTone } from '../display/StatusChip';
import { GPS_STATUS_LABELS, locationAgeSeconds, type GpsEvidenceValues } from './gps';

const GPS_TONES: Readonly<Record<GpsStatus, StatusTone>> = {
  FIX: 'success',
  NO_FIX: 'warning',
  TIMEOUT: 'warning',
  PERMISSION_DENIED: 'warning',
  DISABLED: 'warning',
};

/** The recorded GPS attempt for a reading: status, coordinates, accuracy and fix age. */
export function GpsEvidence({ value, timeZone }: { value: GpsEvidenceValues; timeZone: string }) {
  const age = locationAgeSeconds(value);
  const hasCoords = value.latitude !== null && value.longitude !== null;
  return (
    <Stack spacing={1}>
      <div>
        <StatusChip
          status={value.gps_status}
          tones={GPS_TONES}
          label={GPS_STATUS_LABELS[value.gps_status]}
        />
      </div>
      <KeyValueGrid
        columns={2}
        items={[
          {
            label: 'Coordinates',
            value: hasCoords
              ? `${String(value.latitude)}, ${String(value.longitude)}`
              : 'None recorded (no coordinates are ever substituted)',
          },
          {
            label: 'Accuracy',
            value: value.accuracy_m === null ? '—' : `±${String(value.accuracy_m)} m`,
          },
          {
            label: 'Fix time',
            value: formatInstantIn(value.location_captured_at, timeZone, true),
          },
          {
            label: 'Location age at reading',
            value: age === null ? '—' : `${String(age)} s`,
          },
        ]}
      />
    </Stack>
  );
}
