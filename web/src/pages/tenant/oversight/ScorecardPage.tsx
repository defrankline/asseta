import { Alert, Box, Stack, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import type { ScorecardRowDto } from '../../../api/oversightTypes';
import { oversightService } from '../../../api/services/oversightService';
import type { JobSiteDto, StaffDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { MoneyText } from '../../../components/display/MoneyText';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { scorecardPersonPath } from '../../../navigation/oversightRoutes';
import { labelOf, STAFF_KIND_OPTIONS } from '../shared/display';
import { StaffFilter } from '../shared/financePickers';
import { JobSiteFilter } from '../shared/lookupPickers';
import { nameOr } from '../shared/names';
import { isDay, periodError } from './oversightDisplay';
import { AmountsCell, PeriodFields } from './oversightParts';

const muted = (text: string) => (
  <Typography variant="caption" color="text.secondary" component="div">
    {text}
  </Typography>
);

function Person({ r }: { r: ScorecardRowDto }) {
  const extra = [r.employee_code, labelOf(STAFF_KIND_OPTIONS, r.staff_kind)]
    .filter((p): p is string => p !== null && p !== '')
    .join(' · ');
  return (
    <Box>
      <span>{nameOr(r.staff_member_name, r.staff_member_id)}</span>
      {muted(r.is_active ? extra : `${extra} · inactive`)}
    </Box>
  );
}

const columns: DataColumn<ScorecardRowDto>[] = [
  { id: 'person', header: 'Person', render: (r) => <Person r={r} /> },
  { id: 'machines', header: 'Machines', align: 'right', render: (r) => r.machines },
  {
    id: 'reports',
    header: 'Daily reports missing / late',
    align: 'right',
    render: (r) => `${String(r.daily_reports_missing)} / ${String(r.daily_reports_late)}`,
  },
  {
    id: 'unexplained',
    header: 'Unexplained engine h',
    align: 'right',
    render: (r) => (
      <Box>
        <span className="font-mono">{r.unexplained_hours}</span>
        {r.unexplained_items > 0 && muted(`${String(r.unexplained_items)} items`)}
      </Box>
    ),
  },
  {
    id: 'alerts',
    header: 'Alerts',
    align: 'right',
    render: (r) => (
      <Box>
        <span>{r.alerts}</span>
        {r.alerts > 0 && muted(`${String(r.alerts_open)} open`)}
        {r.avg_hours_to_acknowledge !== null &&
          muted(`${r.avg_hours_to_acknowledge} h to acknowledge on average`)}
      </Box>
    ),
  },
  {
    id: 'cash_held',
    header: 'Cash held now',
    align: 'right',
    render: (r) =>
      (r.cash_held ?? []).length === 0
        ? '—'
        : (r.cash_held ?? []).map((c) => (
            <Box key={c.currency}>
              <MoneyText amount={c.amount} currency={c.currency} />
              {c.held_days !== null && muted(`oldest ${String(c.held_days)} days`)}
            </Box>
          )),
  },
  {
    id: 'held_too_long',
    header: 'Cash held too long',
    align: 'right',
    render: (r) => r.cash_held_too_long,
  },
  {
    id: 'cash_diff',
    header: 'Cash differences',
    align: 'right',
    render: (r) => (
      <Box>
        <AmountsCell count={r.cash_differences} totals={r.cash_difference_totals} />
        {r.cash_differences_near_threshold > 0 &&
          muted(`${String(r.cash_differences_near_threshold)} just under the case threshold`)}
      </Box>
    ),
  },
  {
    id: 'revenue_diff',
    header: 'Revenue differences',
    align: 'right',
    render: (r) => (
      <AmountsCell count={r.revenue_differences} totals={r.revenue_difference_totals} />
    ),
  },
  { id: 'refused', header: 'Refused attempts', align: 'right', render: (r) => r.refused_attempts },
  {
    id: 'checkins',
    header: 'Check-ins missed',
    align: 'right',
    render: (r) =>
      r.checkins_missed === null ? (
        '—'
      ) : (
        <Box>
          <span>{r.checkins_missed}</span>
          {muted(`${String(r.checkins_made)} made`)}
        </Box>
      ),
  },
  {
    id: 'patterns',
    header: 'Repeats raised',
    align: 'right',
    render: (r) => r.pattern_signals,
  },
  {
    id: 'total',
    header: 'Items to look at',
    align: 'right',
    render: (r) => <strong>{r.items_total}</strong>,
  },
];

/**
 * People scorecard (DEC-031 M1): per person, for a period, the items to look at on the machines and
 * cash they were responsible for. Most items first. Counts only, never a verdict.
 */
export function ScorecardPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [from, setFrom] = useState(() => params.get('day_from') ?? '');
  const [to, setTo] = useState(() => params.get('day_to') ?? '');
  const [staff, setStaff] = useState<StaffDto | null>(null);
  const [site, setSite] = useState<JobSiteDto | null>(null);
  const fetchPage = useCallback<FetchPage<ScorecardRowDto>>(
    (query, signal) => oversightService.listScorecard(query, signal),
    [],
  );
  const problem = periodError(from, to);
  const dayFrom = isDay(from) && problem === null ? from : undefined;
  const dayTo = isDay(to) && problem === null ? to : undefined;
  const setPeriod = (key: 'day_from' | 'day_to', value: string) => {
    const next = new URLSearchParams(params);
    if (isDay(value)) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };
  return (
    <>
      <PageHeader
        title="People scorecard"
        subtitle="Per person, the items to look at on the machines and cash they were responsible for (default: the last 30 days)"
      />
      <Stack spacing={2}>
        {problem !== null && <Alert severity="error">{problem}</Alert>}
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(r) => r.staff_member_id}
          searchPlaceholder="Search name"
          filters={{
            day_from: dayFrom,
            day_to: dayTo,
            staff_id: staff?.id,
            site_id: site?.id,
          }}
          emptyTitle="No people to show"
          emptyDescription="Active staff and anyone with items in the period appear here."
          isRowMuted={(r) => r.items_total === 0}
          onRowClick={(r) => {
            void navigate(
              scorecardPersonPath(r.staff_member_id, { day_from: dayFrom, day_to: dayTo }),
            );
          }}
          toolbar={
            <Box className="flex flex-wrap items-center gap-3">
              <PeriodFields
                from={from}
                to={to}
                onFrom={(v) => {
                  setFrom(v);
                  setPeriod('day_from', v);
                }}
                onTo={(v) => {
                  setTo(v);
                  setPeriod('day_to', v);
                }}
              />
              <Box sx={{ minWidth: 220 }}>
                <StaffFilter label="Person" value={staff} onChange={setStaff} />
              </Box>
              <Box sx={{ minWidth: 220 }}>
                <JobSiteFilter label="Site" value={site} onChange={setSite} />
              </Box>
            </Box>
          }
        />
      </Stack>
    </>
  );
}
