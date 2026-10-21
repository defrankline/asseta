import { Alert, Button, Paper, Stack, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { JobSummaryDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { HoursComparison } from '../../../components/meter/HoursComparison';
import { exceptionsPath } from '../../../navigation/routes';
import { formatPercent } from '../../../utils/money';
import { formatInstantIn } from '../../../utils/time';
import { labelOf } from '../shared/display';
import {
  JOB_STATUS_OPTIONS,
  JOB_STATUS_TONES,
  rateSourceLabel,
  STANDBY_OPTIONS,
} from '../shared/jobDisplay';

interface JobSummaryPanelProps {
  summary: JobSummaryDto;
  machineName: string;
  siteName: string;
  timeZone: string;
  canSeeExceptions: boolean;
}

/** Status, price snapshot, readings, hours and billing readiness from getJobSummary. */
export function JobSummaryPanel({
  summary,
  machineName,
  siteName,
  timeZone,
  canSeeExceptions,
}: JobSummaryPanelProps) {
  const job = summary.job;
  const money = (amount: string) => <MoneyText amount={amount} currency={job.currency} />;
  return (
    <Stack spacing={2}>
      <Paper variant="outlined" className="p-4">
        <Stack spacing={2}>
          <KeyValueGrid
            columns={4}
            items={[
              {
                label: 'Status',
                value: (
                  <StatusChip
                    status={job.status}
                    tones={JOB_STATUS_TONES}
                    label={labelOf(JOB_STATUS_OPTIONS, job.status)}
                  />
                ),
              },
              { label: 'Machine', value: machineName },
              { label: 'Job site', value: siteName },
              { label: 'Planned start', value: formatInstantIn(job.planned_start, timeZone) },
              { label: 'Planned end', value: formatInstantIn(job.planned_end, timeZone) },
              { label: 'Started', value: formatInstantIn(job.started_at, timeZone) },
              { label: 'Completed', value: formatInstantIn(job.completed_at, timeZone) },
              { label: 'Approved', value: formatInstantIn(job.approved_at, timeZone) },
            ]}
          />
          <Typography variant="subtitle2" component="h3">
            Price snapshot
          </Typography>
          <KeyValueGrid
            columns={4}
            items={[
              { label: 'Hourly rate', value: money(job.hourly_rate) },
              { label: 'Rate source', value: rateSourceLabel(job.rate_source) },
              { label: 'Minimum hours', value: `${job.minimum_hours} h` },
              { label: 'Standby', value: labelOf(STANDBY_OPTIONS, job.standby_treatment) },
              {
                label: 'Standby rate',
                value: job.standby_rate === null ? '—' : money(job.standby_rate),
              },
              { label: 'Mobilization fee', value: money(job.mobilization_fee) },
              { label: 'Discount', value: formatPercent(job.discount_percent) },
              { label: 'Tax rate', value: formatPercent(job.tax_rate_percent) },
            ]}
          />
        </Stack>
      </Paper>
      <Paper variant="outlined" className="p-4">
        <Stack spacing={2}>
          <Typography variant="subtitle2" component="h3">
            Readings and hours
          </Typography>
          <KeyValueGrid
            columns={3}
            items={[
              { label: 'Opening reading', value: summary.opening_reading ?? 'Not recorded' },
              { label: 'Closing reading', value: summary.closing_reading ?? 'Not recorded' },
              { label: 'Billing policy version', value: summary.policy_version },
            ]}
          />
          <HoursComparison
            meterHours={summary.meter_hours}
            nonbillableHours={summary.nonbillable_hours}
            billableHours={summary.billable_hours}
            minimumHours={job.minimum_hours}
          />
          <Stack direction="row" spacing={1} className="flex-wrap items-center">
            {summary.billing_ready ? (
              <StatusChip status="READY" tones={{ READY: 'success' }} label="Billing ready" />
            ) : (
              <StatusChip status="NOT_READY" label="Not billing ready" />
            )}
            <StatusChip
              status={summary.open_exceptions > 0 ? 'OPEN' : 'NONE'}
              tones={{ OPEN: 'warning' }}
              label={`${String(summary.open_exceptions)} open exception(s)`}
            />
            <StatusChip
              status={summary.blocking_exceptions > 0 ? 'BLOCKING' : 'NONE'}
              tones={{ BLOCKING: 'warning' }}
              label={`${String(summary.blocking_exceptions)} blocking billing`}
            />
            {canSeeExceptions && summary.open_exceptions > 0 && (
              <Button size="small" component={RouterLink} to={exceptionsPath(job.id)}>
                Review exceptions
              </Button>
            )}
          </Stack>
          {!summary.billing_ready && job.status === 'COMPLETED' && (
            <Alert severity="info">
              Billing needs a completed job with both readings and no open blocking exceptions.
              Blocking exceptions require review before billing.
            </Alert>
          )}
        </Stack>
      </Paper>
    </Stack>
  );
}
