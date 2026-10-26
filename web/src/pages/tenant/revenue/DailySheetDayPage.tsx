import { Button, Link, Typography } from '@mui/material';
import { useCallback } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { revenueService } from '../../../api/services/revenueService';
import type {
  DailyMachineSheetDetailDto,
  SheetFuelDto,
  SheetJobDto,
  SheetReadingDto,
  SheetSegmentDto,
} from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import {
  DetailSection,
  EntityDetailsLayout,
} from '../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { engineHoursMachinePath, jobDetailPath, ROUTES } from '../../../navigation/routes';
import { formatDate } from '../../../utils/dates';
import { formatInstantIn } from '../../../utils/time';
import { humanize } from '../../../utils/text';
import { CLASSIFICATION_LABELS } from '../engineHours/engineHoursDisplay';
import type { SegmentClassification } from '../../../api/types';
import { MoneySourcesTable } from './moneySources';
import { hoursByTypeText } from './revenueDisplay';
import { differenceMachine } from './revenueDisplay';
import { RecordFlags } from './sheetParts';

const jobCell = (jobId: string | null, jobNumber: string | null | undefined) =>
  jobId === null ? (
    '—'
  ) : (
    <Link component={RouterLink} to={jobDetailPath(jobId)}>
      {jobNumber ?? 'Open job'}
    </Link>
  );

const SEGMENT_KIND_LABELS: Readonly<Record<string, string>> = {
  CUSTOMER_WORK: 'Customer work',
  UNALLOCATED: 'Outside jobs',
  NON_REVENUE: 'Non-revenue time',
};

const classificationText = (c: string): string =>
  c in CLASSIFICATION_LABELS ? CLASSIFICATION_LABELS[c as SegmentClassification] : humanize(c);

function Sections({ d, timeZone }: { d: DailyMachineSheetDetailDto; timeZone: string }) {
  const readingColumns: DataColumn<SheetReadingDto>[] = [
    { id: 'at', header: 'Taken', render: (r) => formatInstantIn(r.captured_at, timeZone) },
    {
      id: 'reading',
      header: 'Reading',
      align: 'right',
      render: (r) => <span className="font-mono">{r.reading}</span>,
    },
    { id: 'kind', header: 'Kind', render: (r) => humanize(r.kind) },
    { id: 'state', header: 'State', render: (r) => humanize(r.state) },
    { id: 'job', header: 'Job', render: (r) => jobCell(r.job_id, r.job_number) },
  ];
  const segmentColumns: DataColumn<SheetSegmentDto>[] = [
    {
      id: 'when',
      header: 'Between readings',
      render: (s) =>
        `${formatInstantIn(s.start_at, timeZone)} → ${formatInstantIn(s.end_at, timeZone)}`,
    },
    { id: 'kind', header: 'Kind', render: (s) => SEGMENT_KIND_LABELS[s.kind] ?? humanize(s.kind) },
    { id: 'class', header: 'Explained as', render: (s) => classificationText(s.classification) },
    {
      id: 'hours',
      header: 'Hours this day',
      align: 'right',
      render: (s) => <span className="font-mono">{s.hours_in_day}</span>,
    },
    {
      id: 'customer',
      header: 'Customer work',
      align: 'right',
      render: (s) => <span className="font-mono">{s.customer_work_hours_in_day}</span>,
    },
    { id: 'nonrev', header: 'Non-revenue', render: (s) => hoursByTypeText(s.non_revenue_by_type) },
    { id: 'job', header: 'Job', render: (s) => jobCell(s.job_id, s.job_number) },
  ];
  const jobColumns: DataColumn<SheetJobDto>[] = [
    { id: 'job', header: 'Job', render: (j) => jobCell(j.job_id, j.job_number) },
    { id: 'customer', header: 'Customer', render: (j) => j.customer_name ?? '—' },
    { id: 'site', header: 'Site', render: (j) => j.job_site_name ?? '—' },
    { id: 'billing', header: 'Billing', render: (j) => humanize(j.billing_mode) },
    { id: 'status', header: 'Status', render: (j) => humanize(j.status) },
    {
      id: 'customer_hours',
      header: 'Customer work h',
      align: 'right',
      render: (j) => <span className="font-mono">{j.customer_work_hours}</span>,
    },
    {
      id: 'revenue_hours',
      header: 'Revenue h',
      align: 'right',
      render: (j) => <span className="font-mono">{j.revenue_hours}</span>,
    },
  ];
  const fuelColumns: DataColumn<SheetFuelDto>[] = [
    { id: 'at', header: 'When', render: (f) => formatInstantIn(f.occurred_at, timeZone) },
    { id: 'type', header: 'Type', render: (f) => humanize(f.event_type) },
    {
      id: 'litres',
      header: 'Litres',
      align: 'right',
      render: (f) => <span className="font-mono">{f.litres}</span>,
    },
    { id: 'job', header: 'Job', render: (f) => jobCell(f.job_id, null) },
  ];
  const empty = (text: string) => (
    <Typography variant="body2" color="text.secondary">
      {text}
    </Typography>
  );
  return (
    <>
      <DetailSection title="Hours">
        <KeyValueGrid
          columns={4}
          items={[
            { label: 'Engine hours', value: `${d.engine_hours} h` },
            { label: 'Customer work', value: `${d.customer_work_hours} h` },
            { label: 'Revenue hours', value: `${d.revenue_hours} h` },
            {
              label: 'Non-revenue time',
              value: `${d.non_revenue_hours} h (${hoursByTypeText(d.non_revenue_by_type)})`,
            },
            {
              label: 'Non-revenue awaiting approval',
              value: `${d.non_revenue_pending_hours} h (counted as revenue)`,
            },
            { label: 'Non-customer activity', value: `${d.approved_non_customer_hours} h` },
            { label: 'Identified variance', value: `${d.identified_variance_hours} h` },
            { label: 'Not yet explained', value: `${d.unexplained_hours} h` },
            { label: 'Readings under review', value: `${d.pending_review_hours} h` },
            {
              label: 'Readings',
              value:
                d.reading_count === 0
                  ? 'None'
                  : `${d.first_reading ?? '—'} → ${d.last_reading ?? '—'} (${String(d.reading_count)})`,
            },
            { label: 'Fuel into the machine', value: `${d.fuel_litres} L` },
          ]}
        />
      </DetailSection>
      <DetailSection title="Money">
        {d.money.length === 0
          ? empty('No expected revenue or money for this day.')
          : d.money.map((m) => (
              <KeyValueGrid
                key={m.currency}
                columns={4}
                items={[
                  {
                    label: `Expected (${m.currency})`,
                    value: <MoneyText amount={m.expected} currency={m.currency} />,
                  },
                  {
                    label: 'Of which unexplained hours',
                    value: (
                      <>
                        <MoneyText amount={m.unexplained_expected} currency={m.currency} /> (
                        {m.unexplained_hours} h)
                      </>
                    ),
                  },
                  {
                    label: 'Work in progress',
                    value: <MoneyText amount={m.in_progress} currency={m.currency} />,
                  },
                  {
                    label: 'Attributed',
                    value: <MoneyText amount={m.attributed} currency={m.currency} />,
                  },
                  {
                    label: 'Difference',
                    value: <MoneyText amount={m.difference} currency={m.currency} strong />,
                  },
                ]}
              />
            ))}
      </DetailSection>
      <DetailSection title="Flags">
        <RecordFlags flags={d.flags} refs={d.flag_records} machineId={d.machine_id} />
      </DetailSection>
      <DetailSection title="Jobs">
        {d.jobs.length === 0 ? (
          empty('No jobs on this machine this day.')
        ) : (
          <StaticTable
            ariaLabel="Jobs"
            columns={jobColumns}
            rows={d.jobs}
            getRowId={(j) => j.job_id}
          />
        )}
      </DetailSection>
      <DetailSection title="Money sources">
        {d.money_sources.length === 0 ? (
          empty('No issued invoice lines or prepaid hours used for these jobs yet.')
        ) : (
          <MoneySourcesTable rows={d.money_sources} />
        )}
      </DetailSection>
      <DetailSection title="Engine-hour segments">
        {d.segments.length === 0 ? (
          empty('No engine hours this day.')
        ) : (
          <StaticTable
            ariaLabel="Engine-hour segments"
            columns={segmentColumns}
            rows={d.segments}
            getRowId={(s) => `${s.start_ref}:${s.end_ref}:${s.kind}:${s.job_id ?? ''}`}
          />
        )}
      </DetailSection>
      <DetailSection title="Readings">
        {d.readings.length === 0 ? (
          empty('No readings this day.')
        ) : (
          <StaticTable
            ariaLabel="Readings"
            columns={readingColumns}
            rows={d.readings}
            getRowId={(r) => r.id}
          />
        )}
      </DetailSection>
      <DetailSection title="Fuel">
        {d.fuel_events.length === 0 ? (
          empty('No fuel issued or bought into this machine this day.')
        ) : (
          <StaticTable
            ariaLabel="Fuel"
            columns={fuelColumns}
            rows={d.fuel_events}
            getRowId={(f) => f.id}
          />
        )}
      </DetailSection>
    </>
  );
}

/** One machine-day of the daily sheet: readings, segments, jobs, money sources, fuel and flags. */
export function DailySheetDayPage() {
  const { machineId = '', day = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const load = useCallback(
    (signal: AbortSignal) => revenueService.sheetDay(machineId, day, signal),
    [machineId, day],
  );
  const resource = useAsyncResource(load);
  return (
    <AsyncContent
      resource={resource}
      loadingLabel="Loading the machine's day"
      errorTitle="Could not load this machine-day"
    >
      {(d) => (
        <EntityDetailsLayout
          title={`${differenceMachine(d)} · ${formatDate(d.day)}`}
          subtitle="Daily machine sheet"
          back={{ label: 'Daily machine sheet', to: ROUTES.tenantDailySheet }}
          actions={
            <Button component={RouterLink} to={engineHoursMachinePath(d.machine_id)}>
              Engine hours
            </Button>
          }
        >
          <Sections d={d} timeZone={timeZone} />
        </EntityDetailsLayout>
      )}
    </AsyncContent>
  );
}
