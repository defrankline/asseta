import { Link, Typography } from '@mui/material';
import { Link as RouterLink, useParams } from 'react-router';
import { revenueService } from '../../../api/services/revenueService';
import type { RevenueAdjustmentDto, RevenueDifferenceDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { MoneyText } from '../../../components/display/MoneyText';
import { DetailSection } from '../../../components/lifecycle/EntityDetailsLayout';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { recordPath } from '../../../navigation/recordRoutes';
import { jobDetailPath, ROUTES } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import { PersonName } from '../shared/PersonName';
import { RecordDetail } from '../shared/RecordDetail';
import { useRecordById } from '../shared/useRecordById';
import { MoneySourcesTable } from './moneySources';
import { parseDifferenceJobs, parseMoneySources, type DifferenceJob } from './revenueDetail';
import { ADJUSTMENT_CAUSE_LABELS } from './revenueDisplay';
import { differenceMachine, differencePeriod } from './revenueDisplay';
import { approvalChip, differenceChip, useApprovalKit, useDifferenceKit } from './revenueKits';

const loadDifference = (id: string, signal: AbortSignal) =>
  revenueService.getDifference(id, signal);
const loadApproval = (id: string, signal: AbortSignal) => revenueService.getApproval(id, signal);

const jobColumns: DataColumn<DifferenceJob>[] = [
  {
    id: 'job',
    header: 'Job',
    render: (j) => (
      <Link component={RouterLink} to={jobDetailPath(j.job_id)}>
        {j.job_number ?? 'Open job'}
      </Link>
    ),
  },
  { id: 'state', header: 'State', render: (j) => (j.completed ? 'Completed' : 'Running') },
  {
    id: 'expected',
    header: 'Expected',
    align: 'right',
    render: (j) => <MoneyText amount={j.expected} currency={j.currency} />,
  },
  {
    id: 'progress',
    header: 'In progress',
    align: 'right',
    render: (j) => <MoneyText amount={j.in_progress} currency={j.currency} />,
  },
  {
    id: 'attributed',
    header: 'Attributed',
    align: 'right',
    render: (j) => <MoneyText amount={j.attributed} currency={j.currency} />,
  },
];

function adjustmentColumns(
  d: RevenueDifferenceDto,
  timeZone: string,
): DataColumn<RevenueAdjustmentDto>[] {
  const cause = (a: RevenueAdjustmentDto) => {
    const label = ADJUSTMENT_CAUSE_LABELS[a.cause_type] ?? a.cause_type;
    if (a.cause_type === 'non_revenue_approval')
      return (
        <Link component={RouterLink} to={recordPath('NON_REVENUE_APPROVAL', a.cause_id)}>
          {label}
        </Link>
      );
    if (a.cause_type === 'engine_hour_classification')
      return (
        <Link component={RouterLink} to={recordPath('ENGINE_HOURS_CLASSIFICATION', a.cause_id)}>
          {label}
        </Link>
      );
    return label;
  };
  return [
    { id: 'at', header: 'When', render: (a) => formatInstantIn(a.created_at, timeZone) },
    { id: 'cause', header: 'Cause', render: cause },
    {
      id: 'previous',
      header: 'Previous',
      align: 'right',
      render: (a) => <MoneyText amount={a.previous_difference} currency={d.currency} />,
    },
    {
      id: 'new',
      header: 'New',
      align: 'right',
      render: (a) => <MoneyText amount={a.new_difference} currency={d.currency} />,
    },
    {
      id: 'amount',
      header: 'Change',
      align: 'right',
      render: (a) => <MoneyText amount={a.amount} currency={d.currency} />,
    },
    {
      id: 'by',
      header: 'By',
      render: (a) => <PersonName userId={a.created_by} name={a.created_by_name} />,
    },
  ];
}

function DifferenceSections({ d, timeZone }: { d: RevenueDifferenceDto; timeZone: string }) {
  const jobs = parseDifferenceJobs(d.detail);
  const sources = parseMoneySources(d.detail);
  const adjustments = d.adjustments ?? [];
  return (
    <>
      <DetailSection title="Jobs">
        {jobs.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No jobs in this period: the expected revenue is from engine hours outside jobs.
          </Typography>
        ) : (
          <StaticTable
            ariaLabel="Jobs"
            columns={jobColumns}
            rows={jobs}
            getRowId={(j) => `${j.job_id}:${j.currency}`}
          />
        )}
      </DetailSection>
      <DetailSection title="Money sources">
        {sources.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No issued invoice lines or prepaid hours used for these jobs yet.
          </Typography>
        ) : (
          <MoneySourcesTable rows={sources} />
        )}
      </DetailSection>
      <DetailSection title="Adjustments">
        {adjustments.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No later changes. When hours are explained after a decision, the change is recorded here
            (the decided figures are never rewritten).
          </Typography>
        ) : (
          <StaticTable
            ariaLabel="Adjustments"
            columns={adjustmentColumns(d, timeZone)}
            rows={adjustments}
            getRowId={(a) => a.id}
          />
        )}
      </DetailSection>
    </>
  );
}

/** One revenue difference (exact-record link): figures, explain / decide, jobs, money, adjustments. */
export function RevenueDifferenceDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(loadDifference, id);
  const kit = useDifferenceKit(res.reload);
  return (
    <>
      <RecordDetail
        resource={res}
        what="revenue difference"
        back={{ label: 'Revenue differences', to: ROUTES.tenantRevenueDifferences }}
        timeZone={timeZone}
        title={(d) => `Difference · ${differenceMachine(d)}`}
        subtitle={differencePeriod}
        status={differenceChip}
        actions={kit.actionsFor}
        primaryKey="explain"
        links={kit.links}
        items={kit.items}
        history={kit.history}
      >
        {(d) => <DifferenceSections d={d} timeZone={timeZone} />}
      </RecordDetail>
      {kit.dialog}
    </>
  );
}

/** One explanation of non-revenue time (exact-record link): details, decide, history. */
export function NonRevenueApprovalDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(loadApproval, id);
  const kit = useApprovalKit(res.reload);
  return (
    <>
      <RecordDetail
        resource={res}
        what="non-revenue approval"
        back={{ label: 'Non-revenue hours', to: ROUTES.tenantNonRevenueApprovals }}
        timeZone={timeZone}
        title={(a) => `Non-revenue time · ${a.hours} h · ${differenceMachine(a)}`}
        status={approvalChip}
        actions={kit.actionsFor}
        primaryKey="decide"
        items={kit.items}
        history={kit.history}
      />
      {kit.dialog}
    </>
  );
}
