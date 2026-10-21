import { Alert } from '@mui/material';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { formatPercent } from '../../../utils/money';
import { formatInstantIn } from '../../../utils/time';
import { labelOf, machineLabel } from '../shared/display';
import { contractLabel, STANDBY_OPTIONS } from '../shared/jobDisplay';
import type { JobFormValues } from './jobForm';

function money(amount: string, currency: string | undefined) {
  return currency === undefined ? amount : <MoneyText amount={amount} currency={currency} />;
}

/** Review step of the job form (create and edit). */
export function JobReview({
  v,
  timeZone,
  siteLabel,
}: {
  v: JobFormValues;
  timeZone: string;
  siteLabel: (id: string | null) => string;
}) {
  const currency = v.contract?.currency;
  const negotiated = v.rate_mode === 'NEGOTIATED';
  return (
    <>
      <Alert severity={negotiated ? 'warning' : 'info'}>
        {negotiated ? (
          <>
            Rate source: <strong>Negotiated</strong> — {money(v.hourly_rate.trim(), currency)} per
            hour for this job only (overrides the rate card).
          </>
        ) : (
          <>
            Rate source: <strong>Tenant rate card</strong> — resolved by the server for the
            machine&apos;s category at the planned start and snapshotted on the job.
          </>
        )}
      </Alert>
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Contract', value: v.contract === null ? '—' : contractLabel(v.contract) },
          { label: 'Job number', value: v.job_number.trim() },
          { label: 'Machine', value: v.machine === null ? '—' : machineLabel(v.machine) },
          { label: 'Supervisor', value: v.supervisor?.full_name ?? '—' },
          {
            label: 'Job site',
            value: v.job_site_id === '' ? "Contract's default" : siteLabel(v.job_site_id),
          },
          { label: 'Planned start', value: formatInstantIn(v.planned_start, timeZone) },
          {
            label: 'Planned end',
            value: v.planned_end === '' ? '—' : formatInstantIn(v.planned_end, timeZone),
          },
          {
            label: 'Hourly rate',
            value: negotiated ? money(v.hourly_rate.trim(), currency) : 'From rate card',
          },
          {
            label: 'Minimum hours',
            value:
              v.minimum_hours.trim() === ''
                ? negotiated
                  ? 'None'
                  : 'From rate card'
                : `${v.minimum_hours.trim()} h`,
          },
          { label: 'Standby', value: labelOf(STANDBY_OPTIONS, v.standby_treatment) },
          ...(v.standby_treatment === 'STANDBY_RATE'
            ? [{ label: 'Standby rate', value: money(v.standby_rate.trim(), currency) }]
            : []),
          { label: 'Mobilization fee', value: money(v.mobilization_fee.trim(), currency) },
          { label: 'Discount', value: formatPercent(v.discount_percent.trim()) },
          { label: 'Tax rate', value: formatPercent(v.tax_rate_percent.trim()) },
        ]}
      />
    </>
  );
}
