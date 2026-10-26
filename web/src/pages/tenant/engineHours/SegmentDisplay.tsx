import { Box, Chip } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { IntervalDto, SegmentDto } from '../../../api/types';
import { StatusChip } from '../../../components/display/StatusChip';
import { jobDetailPath } from '../../../navigation/routes';
import { activityTypeLabel } from '../revenue/revenueDisplay';
import {
  CLASSIFICATION_LABELS,
  CLASSIFICATION_TONES,
  hoursText,
  OUTCOME_LABELS,
} from './engineHoursDisplay';

/** One segment of an engine-hour interval: customer work, non-revenue time in a job, or unallocated. */
export function SegmentChip({ segment }: { segment: SegmentDto }) {
  if (segment.kind === 'NON_REVENUE') {
    const type =
      segment.activity_type == null ? 'Non-revenue' : activityTypeLabel(segment.activity_type);
    const label = `${type} · Job ${segment.job_number ?? '—'} · ${hoursText(segment.hours)}`;
    return segment.job_id === null ? (
      <Chip size="small" color="secondary" label={label} />
    ) : (
      <Chip
        size="small"
        color="secondary"
        label={label}
        component={RouterLink}
        to={jobDetailPath(segment.job_id)}
        clickable
      />
    );
  }
  if (segment.kind === 'CUSTOMER_WORK') {
    const label = `Job ${segment.job_number ?? '—'} · ${hoursText(segment.hours)}`;
    return segment.job_id === null ? (
      <Chip size="small" color="success" label={label} />
    ) : (
      <Chip
        size="small"
        color="success"
        label={label}
        component={RouterLink}
        to={jobDetailPath(segment.job_id)}
        clickable
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
  CUSTOMER_WORK: 'customer work',
  UNALLOCATED: 'unallocated',
  NON_REVENUE: 'non-revenue',
};

/** Proportional bar of an interval's segments (customer work vs unallocated), labelled for screen readers. */
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
              s.kind === 'CUSTOMER_WORK'
                ? 'success.main'
                : s.kind === 'NON_REVENUE'
                  ? 'secondary.main'
                  : s.classification === 'UNEXPLAINED'
                    ? 'warning.main'
                    : 'info.main',
          }}
        />
      ))}
    </Box>
  );
}
