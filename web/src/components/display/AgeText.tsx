import { Box, Tooltip } from '@mui/material';
import { ageSecondsSince, formatAge, formatInstantIn } from '../../utils/time';

interface AgeTextProps {
  /** UTC ISO instant. */
  at: string | null;
  /** Current time in ms (pass `useNow()` so ages tick). */
  now: number;
  /** IANA zone for the exact-time tooltip. */
  timeZone: string;
  /** Text when `at` is null. */
  emptyLabel?: string;
}

/** Relative age (`12 min ago`) with the exact local time on hover. */
export function AgeText({ at, now, timeZone, emptyLabel = 'never' }: AgeTextProps) {
  if (at === null) {
    return (
      <Box component="span" sx={{ color: 'text.secondary' }}>
        {emptyLabel}
      </Box>
    );
  }
  return (
    <Tooltip title={formatInstantIn(at, timeZone, true)}>
      <Box component="time" dateTime={at} sx={{ whiteSpace: 'nowrap' }}>
        {formatAge(ageSecondsSince(at, now))}
      </Box>
    </Tooltip>
  );
}
