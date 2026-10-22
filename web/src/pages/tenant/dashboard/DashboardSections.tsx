import { Alert, Box, Typography } from '@mui/material';
import { useId, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import type {
  OverviewCurrencyMoneyDto,
  OverviewFleetSectionDto,
  OverviewMoneySectionDto,
  OverviewRiskSectionDto,
  OverviewSeverityCountsDto,
  OverviewWorkSectionDto,
} from '../../../api/types';
import { MoneyText } from '../../../components/display/MoneyText';
import type { StatusTone } from '../../../components/display/StatusChip';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { formatDate } from '../../../utils/dates';
import { formatMoney } from '../../../utils/money';
import { humanize } from '../../../utils/text';
import { formatAge, formatInstantIn } from '../../../utils/time';
import { JOB_STATUS_OPTIONS, JOB_STATUS_TONES } from '../shared/jobDisplay';
import {
  CONNECTIVITY_ROWS,
  DASHBOARD_LINKS as L,
  freshness,
  SEVERITY_ROWS,
  STALE_AFTER_LABEL,
  total,
  type SectionKey,
} from './dashboardModel';
import { KpiCard, type KpiRow } from './KpiCard';

export type Can = (permission: string) => boolean;

const SEVERITY_TONES: Readonly<Record<string, StatusTone>> = {
  CRITICAL: 'error',
  WARNING: 'warning',
  INFO: 'info',
};

const GRID = 'grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4';

interface ShellProps {
  section: SectionKey;
  title: string;
  latest: string | null;
  nowMs: number;
  timeZone: string;
  children: ReactNode;
}

/** A dashboard section: heading, how fresh its newest source record is, and its cards. */
function SectionShell({ section, title, latest, nowMs, timeZone, children }: ShellProps) {
  const headingId = useId();
  const fresh = freshness(latest, nowMs, section);
  return (
    <Box component="section" aria-labelledby={headingId} data-section={section}>
      <Box className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <Typography id={headingId} variant="h6" component="h2">
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {latest === null
            ? 'No source data yet'
            : `Latest data ${formatInstantIn(latest, timeZone)} (${formatAge(
                fresh.ageMs === null ? null : Math.floor(fresh.ageMs / 1000),
              )})`}
        </Typography>
      </Box>
      {fresh.stale && (
        <Alert severity="warning" className="mb-2" data-testid={`stale-${section}`}>
          No new {title.toLowerCase()} data for more than {STALE_AFTER_LABEL[section]}; these
          figures may be out of date.
        </Alert>
      )}
      <Box className={GRID}>{children}</Box>
    </Box>
  );
}

function severityRows(
  counts: OverviewSeverityCountsDto,
  link: ((severity: string) => string) | null,
): KpiRow[] {
  return SEVERITY_ROWS.map((s) => ({
    key: s.value,
    label: s.label,
    value: counts[s.key],
    valueText: String(counts[s.key]),
    tone: SEVERITY_TONES[s.value] ?? 'default',
    to: link?.(s.value),
  }));
}

const sevTotal = (c: OverviewSeverityCountsDto) => c.critical + c.warning + c.info;

interface SectionProps<T> {
  data: T;
  can: Can;
  nowMs: number;
  timeZone: string;
}

export function FleetSection({
  data,
  can,
  nowMs,
  timeZone,
}: SectionProps<OverviewFleetSectionDto>) {
  const alerts = sevTotal(data.open_alerts);
  const states = Object.entries(data.reported_work_state).sort(([a], [b]) => a.localeCompare(b));
  return (
    <SectionShell
      section="fleet"
      title="Fleet"
      latest={data.latest_source_at}
      {...{ nowMs, timeZone }}
    >
      <KpiCard
        title="Machines"
        value={data.machines}
        valueText={String(data.machines)}
        to={L.fleet()}
        rows={CONNECTIVITY_ROWS.map((r) => ({
          key: r.key,
          label: r.label,
          value: data.connectivity[r.key],
          valueText: String(data.connectivity[r.key]),
          to: L.fleet(r.filter),
        }))}
      />
      <KpiCard
        title="Reported work state"
        description="As reported by supervisors"
        rows={states.map(([state, n]) => ({
          key: state,
          label: humanize(state),
          value: n,
          valueText: String(n),
          to: L.fleet(),
        }))}
      />
      <KpiCard
        title="Engine on (verified)"
        value={data.engine_on_verified}
        valueText={String(data.engine_on_verified)}
        to={L.fleet()}
        description="Verified ignition input with a fresh position; never inferred"
      />
      <KpiCard
        title="Open alerts"
        value={alerts}
        valueText={String(alerts)}
        to={can(PERMISSIONS.tenantFleetRead) ? L.openAlerts() : undefined}
        rows={severityRows(
          data.open_alerts,
          can(PERMISSIONS.tenantFleetRead) ? L.openAlerts : null,
        )}
      />
    </SectionShell>
  );
}

export function WorkSection({ data, nowMs, timeZone }: SectionProps<OverviewWorkSectionDto>) {
  const jobs = total(data.jobs_by_status);
  return (
    <SectionShell
      section="work"
      title="Work"
      latest={data.latest_source_at}
      {...{ nowMs, timeZone }}
    >
      <KpiCard
        title="Jobs"
        value={jobs}
        valueText={String(jobs)}
        to={L.jobs()}
        rows={JOB_STATUS_OPTIONS.map((o) => {
          const n = data.jobs_by_status[o.value] ?? 0;
          return {
            key: o.value,
            label: o.label,
            value: n,
            valueText: String(n),
            tone: JOB_STATUS_TONES[o.value],
            to: L.jobs(o.value),
          };
        })}
      />
      {data.pending_approvals !== null && (
        <KpiCard
          title="Pending approvals"
          value={data.pending_approvals}
          valueText={String(data.pending_approvals)}
          to={L.approvals()}
          description="Requests waiting for a decision"
        />
      )}
      {data.readings_needing_review !== null && (
        <KpiCard
          title="Readings needing review"
          value={data.readings_needing_review}
          valueText={String(data.readings_needing_review)}
          to={L.openExceptions()}
          description="Provisional meter readings with an open exception"
        />
      )}
      {data.open_exceptions !== null && (
        <KpiCard
          title="Open exceptions"
          value={data.open_exceptions}
          valueText={String(data.open_exceptions)}
          to={L.openExceptions()}
          description="Meter and GPS exceptions awaiting review"
        />
      )}
    </SectionShell>
  );
}

function money(amount: string, currency: string) {
  return {
    value: <MoneyText amount={amount} currency={currency} />,
    valueText: formatMoney(amount, currency),
  };
}

function CurrencyCard({ c, can }: { c: OverviewCurrencyMoneyDto; can: Can }) {
  const rows: KpiRow[] = [
    {
      key: 'outstanding',
      label: 'Receivables outstanding',
      ...money(c.receivables_outstanding, c.currency),
      to: L.receivables(),
    },
    {
      key: 'overdue',
      label: `Overdue (${String(c.overdue_invoices)} ${c.overdue_invoices === 1 ? 'invoice' : 'invoices'})`,
      ...money(c.receivables_overdue, c.currency),
      to: L.overdue(),
    },
    {
      key: 'receipts',
      label: 'Receipts this month',
      ...money(c.verified_receipts_mtd, c.currency),
      to: L.receipts(),
    },
    {
      key: 'expenses',
      label: 'Approved expenses this month',
      ...money(c.approved_expenses_mtd, c.currency),
      to: can(PERMISSIONS.tenantExpenseRead) ? L.approvedExpenses() : undefined,
    },
    {
      key: 'cash',
      label: 'Cash held by supervisors',
      ...money(c.cash_with_supervisors, c.currency),
      to: L.cashCustody(),
    },
  ];
  return <KpiCard title={c.currency} rows={rows} />;
}

export function MoneySection({
  data,
  can,
  nowMs,
  timeZone,
}: SectionProps<OverviewMoneySectionDto>) {
  return (
    <SectionShell
      section="money"
      title="Money"
      latest={data.latest_source_at}
      {...{ nowMs, timeZone }}
    >
      {data.currencies.length === 0 ? (
        <Box className="col-span-full">
          <EmptyState title="No receivables, receipts or expenses yet" />
        </Box>
      ) : (
        data.currencies.map((c) => <CurrencyCard key={c.currency} c={c} can={can} />)
      )}
      <Typography variant="caption" color="text.secondary" className="col-span-full">
        Per currency, never converted or summed across currencies. This month started{' '}
        {formatDate(data.month_start)} ({timeZone}).
      </Typography>
    </SectionShell>
  );
}

export function RiskSection({ data, can, nowMs, timeZone }: SectionProps<OverviewRiskSectionDto>) {
  const canCases = can(PERMISSIONS.tenantCaseRead);
  return (
    <SectionShell
      section="risk"
      title="Risk"
      latest={data.latest_source_at}
      {...{ nowMs, timeZone }}
    >
      {data.open_cases !== null && (
        <KpiCard
          title="Open cases"
          value={sevTotal(data.open_cases)}
          valueText={String(sevTotal(data.open_cases))}
          to={canCases ? L.cases() : undefined}
          description="Unresolved investigations, for human review"
          rows={severityRows(data.open_cases, canCases ? L.cases : null)}
        />
      )}
      {data.signals_last_7_days !== null && (
        <KpiCard
          title="Signals (last 7 days)"
          value={sevTotal(data.signals_last_7_days)}
          valueText={String(sevTotal(data.signals_last_7_days))}
          to={canCases ? L.signals() : undefined}
          description="Deterministic checks that found something to look at"
          rows={severityRows(data.signals_last_7_days, canCases ? L.signals : null)}
        />
      )}
    </SectionShell>
  );
}
