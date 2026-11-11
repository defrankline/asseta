import { Box, Link, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { BookedJobDto } from '../../../api/hoursTypes';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { jobDetailPath } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import { bookedJobStatusLabel } from './purchaseForm';

/** "Start – end" of a booked job ("open-ended" without an end). */
function bookedJobWindow(job: BookedJobDto, timeZone: string): string {
  const end = job.planned_end === null ? 'open-ended' : formatInstantIn(job.planned_end, timeZone);
  return `${formatInstantIn(job.planned_start, timeZone)} – ${end}`;
}

/** The job number, linking to the job. */
function BookedJobLink({ job }: { job: BookedJobDto }) {
  return (
    <Link
      component={RouterLink}
      to={jobDetailPath(job.id)}
      onClick={(e) => {
        // In a clickable list row: open the job, not the purchase.
        e.stopPropagation();
      }}
    >
      {job.job_number}
    </Link>
  );
}

/** List cell: job number (linked) with its status, or a dash. */
export function BookedJobCell({ job }: { job: BookedJobDto | null | undefined }) {
  if (job == null) return <>—</>;
  return (
    <Box component="span" className="inline-flex flex-col">
      <BookedJobLink job={job} />
      <Typography component="span" variant="caption" color="text.secondary">
        {bookedJobStatusLabel(job)}
      </Typography>
    </Box>
  );
}

/** The job booked with a sale: number (linked), status, planned window, contract. */
export function BookedJobDetails({ job, timeZone }: { job: BookedJobDto; timeZone: string }) {
  return (
    <KeyValueGrid
      columns={3}
      items={[
        { label: 'Job', value: <BookedJobLink job={job} /> },
        { label: 'Job status', value: bookedJobStatusLabel(job) },
        { label: 'Planned', value: bookedJobWindow(job, timeZone) },
        { label: 'Contract', value: job.contract_number ?? '—' },
        {
          label: 'Approved at',
          value: job.approved_at === null ? '—' : formatInstantIn(job.approved_at, timeZone),
        },
      ]}
    />
  );
}
