import { Box, Chip } from '@mui/material';
import type { IntervalDto, SegmentDto } from '../../../api/types';
import { StatusChip } from '../../../components/display/StatusChip';
import {
  CLASSIFICATION_LABELS,
  CLASSIFICATION_TONES,
  hoursText,
  OUTCOME_LABELS,
} from './engineHoursDisplay';

/** One segment of an engine-hour interval: inside a machine report, or not yet accounted for. */
export function SegmentChip({ segment }: { segment: SegmentDto }) {
  if (segment.kind === 'REPORTED') {
    const report = segment.report_number == null ? '' : ` (${segment.report_number})`;
    return (
      <Chip
        size="small"
        color="success"
        label={`Machine report${report} · ${hoursText(segment.hours)}`}
      />
    );
  }
  const pending =
    segment.proposal !== null ? ` · ${OUTCOME_LABELS[segment.proposal.outcome]} proposed` : '';
  return (
    <StatusChip
      status={segment.classification}
      tones={CLASSIFICATION_TONES}
      label={`${CLASSIFICATION_LABELS[segment.classification]} · ${hoursText(segment.hours)}${pending}`}
    />
  );
}

const SEGMENT_KIND_TEXT: Readonly<Record<SegmentDto['kind'], string>> = {
  REPORTED: 'in a machine report',
  UNALLOCATED: 'unallocated',
};

/** Proportional bar of an interval's segments (reported vs unallocated), labelled for screen readers. */
export function SegmentBar({ interval }: { interval: IntervalDto }) {
  const total = interval.segments.reduce((sum, s) => sum + Math.max(Number(s.hours), 0), 0);
  if (total <= 0) return null;
  return (
    <Box
      role="img"
      aria-label={interval.segments
        .map((s) => `${SEGMENT_KIND_TEXT[s.kind]} ${s.hours} h`)
        .join(', ')}
      sx={{
        display: 'flex',
        height: 6,
        borderRadius: 1,
        overflow: 'hidden',
        mt: 0.5,
        minWidth: 120,
      }}
    >
      {interval.segments.map((s, i) => (
        <Box
          key={i}
          sx={{
            flexGrow: Math.max(Number(s.hours), 0),
            bgcolor:
              s.kind === 'REPORTED'
                ? 'success.main'
                : s.classification === 'UNEXPLAINED'
                  ? 'warning.main'
                  : 'info.main',
          }}
        />
      ))}
    </Box>
  );
}
