import { Alert, Box, Chip, Link, Stack, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useParams, useSearchParams } from 'react-router';
import { useDisabledCapabilities } from '../../../access/capabilities';
import type {
  ScorecardItem,
  ScorecardRecordDto,
  ScorecardRecordItem,
  ScorecardRowDto,
} from '../../../api/oversightTypes';
import { oversightService } from '../../../api/services/oversightService';
import { StaticTable } from '../../../components/data/StaticTable';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import {
  DetailSection,
  EntityDetailsLayout,
} from '../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { OVERSIGHT_ROUTES } from '../../../navigation/oversightRoutes';
import { jobDetailPath, staffDetailPath } from '../../../navigation/routes';
import { formatDate } from '../../../utils/dates';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import { labelOf, STAFF_KIND_OPTIONS } from '../shared/display';
import { machineText, nameOr } from '../shared/names';
import {
  isDay,
  periodError,
  SCORECARD_ITEM_LABELS,
  SCORECARD_ITEM_OPTIONS,
  SCORECARD_RECORD_ORDER,
  scorecardRecordLink,
} from './oversightDisplay';
import { AmountsCell, PeriodFields } from './oversightParts';

const isItem = (v: string): v is ScorecardItem => SCORECARD_ITEM_OPTIONS.some((o) => o.value === v);

/** The value of one record: money, hours or nothing. */
function RecordValue({ r }: { r: ScorecardRecordDto }) {
  if (r.amount != null && r.currency != null) {
    return <MoneyText amount={r.amount} currency={r.currency} />;
  }
  if (r.hours != null) return <span className="font-mono">{r.hours} h</span>;
  return <span>—</span>;
}

function Figures({ row }: { row: ScorecardRowDto }) {
  return (
    <KeyValueGrid
      columns={4}
      items={[
        { label: 'Machines responsible for', value: String(row.machines) },
        { label: 'Daily reports missing', value: String(row.daily_reports_missing) },
        { label: 'Daily reports late', value: String(row.daily_reports_late) },
        {
          label: 'Unexplained engine hours',
          value: `${row.unexplained_hours} h (${String(row.unexplained_items)} items)`,
        },
        {
          label: 'Tracking alerts',
          value: `${String(row.alerts)} (${String(row.alerts_open)} open, ${String(row.alerts_acknowledged)} acknowledged)`,
        },
        {
          label: 'Hours to acknowledge (average / longest)',
          value:
            row.avg_hours_to_acknowledge === null
              ? '—'
              : `${row.avg_hours_to_acknowledge} / ${row.max_hours_to_acknowledge ?? '—'}`,
        },
        {
          label: 'Cash held now',
          value:
            (row.cash_held ?? []).length === 0
              ? 'None'
              : (row.cash_held ?? []).map((c) => (
                  <Box key={c.currency}>
                    <MoneyText amount={c.amount} currency={c.currency} />
                    {c.held_days !== null && ` · oldest ${String(c.held_days)} days`}
                  </Box>
                )),
        },
        { label: 'Cash held too long (flags)', value: String(row.cash_held_too_long) },
        {
          label: 'Cash differences',
          value: <AmountsCell count={row.cash_differences} totals={row.cash_difference_totals} />,
        },
        {
          label: 'Just under the case threshold',
          value: String(row.cash_differences_near_threshold),
        },
        {
          label: 'Revenue differences',
          value: (
            <AmountsCell count={row.revenue_differences} totals={row.revenue_difference_totals} />
          ),
        },
        { label: 'Refused attempts', value: String(row.refused_attempts) },
        {
          label: 'Site check-ins missed / made',
          value:
            row.checkins_missed === null
              ? 'Not required in the period'
              : `${String(row.checkins_missed)} / ${String(row.checkins_made)}`,
        },
        { label: 'Repeats raised for review', value: String(row.pattern_signals) },
        { label: 'Items to look at', value: String(row.items_total) },
      ]}
    />
  );
}

/**
 * One person's scorecard (DEC-031 M1): the figures for the period and every record behind them,
 * grouped by item, each opening its own page.
 */
export function ScorecardPersonPage() {
  const { staffId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const disabled = useDisabledCapabilities();
  const [params, setParams] = useSearchParams();
  const [from, setFrom] = useState(() => params.get('day_from') ?? '');
  const [to, setTo] = useState(() => params.get('day_to') ?? '');
  const itemParam = params.get('item') ?? '';
  const item = isItem(itemParam) ? itemParam : '';
  const problem = periodError(from, to);
  const dayFrom = isDay(from) && problem === null ? from : undefined;
  const dayTo = isDay(to) && problem === null ? to : undefined;
  const load = useCallback(
    (signal: AbortSignal) =>
      oversightService.getScorecard(
        staffId,
        { day_from: dayFrom, day_to: dayTo, item: item === '' ? undefined : item },
        signal,
      ),
    [staffId, dayFrom, dayTo, item],
  );
  const res = useAsyncResource(load, [staffId, dayFrom, dayTo, item], staffId !== '');
  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value !== '') next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };
  const backTo = (() => {
    const q = new URLSearchParams();
    if (dayFrom !== undefined) q.set('day_from', dayFrom);
    if (dayTo !== undefined) q.set('day_to', dayTo);
    const qs = q.toString();
    return qs === '' ? OVERSIGHT_ROUTES.scorecard : `${OVERSIGHT_ROUTES.scorecard}?${qs}`;
  })();
  const columns: DataColumn<ScorecardRecordDto>[] = [
    { id: 'at', header: 'When', render: (r) => formatInstantIn(r.at, timeZone) },
    { id: 'day', header: 'Day', render: (r) => formatDate(r.day) },
    {
      id: 'machine',
      header: 'Machine',
      render: (r) =>
        r.machine_id == null ? '—' : machineText(r.machine_code, r.machine_name, r.machine_id),
    },
    {
      id: 'job',
      header: 'Job',
      render: (r) =>
        r.job_id == null ? (
          '—'
        ) : (
          <Link component={RouterLink} to={jobDetailPath(r.job_id)}>
            {nameOr(r.job_number, r.job_id)}
          </Link>
        ),
    },
    {
      id: 'value',
      header: 'Amount / hours',
      align: 'right',
      render: (r) => <RecordValue r={r} />,
    },
    {
      id: 'status',
      header: 'Status',
      render: (r) => (
        <Box className="flex flex-wrap gap-1">
          {r.status != null && r.status !== '' ? humanize(r.status) : '—'}
          {r.near_threshold && (
            <Chip size="small" variant="outlined" label="Just under the case threshold" />
          )}
        </Box>
      ),
    },
    {
      id: 'open',
      header: 'Record',
      render: (r) => {
        const link = scorecardRecordLink(r, staffId, disabled);
        return link === null ? (
          '—'
        ) : (
          <Link component={RouterLink} to={link.to}>
            {link.label}
          </Link>
        );
      },
    },
  ];
  return (
    <AsyncContent
      resource={res}
      loadingLabel="Loading scorecard"
      errorTitle="Could not load this person's scorecard"
    >
      {(d) => {
        const byItem = new Map<ScorecardRecordItem, ScorecardRecordDto[]>();
        for (const r of d.records) byItem.set(r.item, [...(byItem.get(r.item) ?? []), r]);
        const groups = SCORECARD_RECORD_ORDER.filter((i) => (byItem.get(i) ?? []).length > 0);
        return (
          <EntityDetailsLayout
            title={nameOr(d.row.staff_member_name, d.row.staff_member_id)}
            subtitle={`${labelOf(STAFF_KIND_OPTIONS, d.row.staff_kind)} · ${formatDate(d.row.day_from)} to ${formatDate(d.row.day_to)}`}
            back={{ label: 'People scorecard', to: backTo }}
            status={
              d.row.is_active ? undefined : (
                <Chip size="small" label="Inactive" variant="outlined" />
              )
            }
            actions={
              <Link component={RouterLink} to={staffDetailPath(d.row.staff_member_id)}>
                Open staff record
              </Link>
            }
          >
            <Box className="flex flex-wrap items-center gap-3">
              <PeriodFields
                from={from}
                to={to}
                onFrom={(v) => {
                  setFrom(v);
                  setParam('day_from', isDay(v) ? v : '');
                }}
                onTo={(v) => {
                  setTo(v);
                  setParam('day_to', isDay(v) ? v : '');
                }}
              />
              <StaticSelectFilter
                label="Item"
                value={item}
                options={SCORECARD_ITEM_OPTIONS}
                allLabel="All items"
                minWidth={220}
                onChange={(v) => {
                  setParam('item', v);
                }}
              />
            </Box>
            {problem !== null && <Alert severity="error">{problem}</Alert>}
            <DetailSection title="Figures for the period">
              <Figures row={d.row} />
            </DetailSection>
            {groups.length === 0 ? (
              <Typography color="text.secondary">No records to look at in this period.</Typography>
            ) : (
              <Stack spacing={2}>
                {groups.map((g) => {
                  const rows = byItem.get(g) ?? [];
                  return (
                    <DetailSection
                      key={g}
                      title={`${SCORECARD_ITEM_LABELS[g]} (${String(rows.length)})`}
                    >
                      <StaticTable
                        columns={columns}
                        rows={rows}
                        getRowId={(r) =>
                          `${r.record_type}-${r.record_id ?? ''}-${r.at}-${r.machine_id ?? ''}`
                        }
                        ariaLabel={SCORECARD_ITEM_LABELS[g]}
                      />
                    </DetailSection>
                  );
                })}
              </Stack>
            )}
          </EntityDetailsLayout>
        );
      }}
    </AsyncContent>
  );
}
