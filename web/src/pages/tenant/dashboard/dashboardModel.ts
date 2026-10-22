import type { OverviewConnectivityCountsDto, OverviewSeverityCountsDto } from '../../../api/types';
import { financeTabPath, ROUTES } from '../../../navigation/routes';
import { withQuery } from '../../../navigation/urlFilters';
import { ENTITY } from '../../../realtime/entities';

export type SectionKey = 'fleet' | 'work' | 'money' | 'risk';

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/**
 * How old a section's newest source record may be before the dashboard says the figures may be out
 * of date: trackers report every few minutes; jobs, money and reviews move daily or weekly.
 */
export const STALE_AFTER_MS: Readonly<Record<SectionKey, number>> = {
  fleet: 2 * HOUR,
  work: 3 * DAY,
  money: 7 * DAY,
  risk: 7 * DAY,
};

export const STALE_AFTER_LABEL: Readonly<Record<SectionKey, string>> = {
  fleet: '2 hours',
  work: '3 days',
  money: '7 days',
  risk: '7 days',
};

/** Records whose changes refresh the dashboard (debounced; positions are frequent). */
export const DASHBOARD_LIVE_ENTITIES: readonly string[] = [
  ENTITY.alert,
  ENTITY.fleetPosition,
  ENTITY.job,
  ENTITY.approval,
  ENTITY.meterCapture,
  ENTITY.meterException,
  ENTITY.hireInvoice,
  ENTITY.customerPayment,
  ENTITY.cashHandover,
  ENTITY.expense,
  ENTITY.anomalyCase,
];

export interface Freshness {
  /** Milliseconds since the newest source record, or null when the section has no source data. */
  ageMs: number | null;
  stale: boolean;
}

export function freshness(latest: string | null, nowMs: number, section: SectionKey): Freshness {
  if (latest === null) return { ageMs: null, stale: false };
  const t = Date.parse(latest);
  if (Number.isNaN(t)) return { ageMs: null, stale: false };
  const ageMs = Math.max(0, nowMs - t);
  return { ageMs, stale: ageMs > STALE_AFTER_MS[section] };
}

/** Connectivity counters of the overview, in display order, with the fleet map filter they open. */
export const CONNECTIVITY_ROWS: readonly {
  key: keyof OverviewConnectivityCountsDto;
  label: string;
  filter: string;
}[] = [
  { key: 'live', label: 'Live', filter: 'LIVE' },
  { key: 'recent', label: 'Recent', filter: 'RECENT' },
  { key: 'stale', label: 'Stale', filter: 'STALE' },
  { key: 'offline', label: 'Offline', filter: 'OFFLINE' },
  { key: 'never', label: 'Never reported', filter: 'NEVER_REPORTED' },
  { key: 'no_tracker', label: 'No tracker', filter: 'NO_TRACKER' },
];

export const SEVERITY_ROWS: readonly {
  key: keyof OverviewSeverityCountsDto;
  label: string;
  value: 'CRITICAL' | 'WARNING' | 'INFO';
}[] = [
  { key: 'critical', label: 'Critical', value: 'CRITICAL' },
  { key: 'warning', label: 'Warning', value: 'WARNING' },
  { key: 'info', label: 'Info', value: 'INFO' },
];

/** Deep links into the filtered list pages behind each figure. */
export const DASHBOARD_LINKS = {
  fleet: (connectivity?: string) => withQuery(ROUTES.tenantFleet, { connectivity }),
  openAlerts: (severity?: string) => withQuery(ROUTES.tenantAlerts, { status: 'OPEN', severity }),
  jobs: (status?: string) => withQuery(ROUTES.tenantJobs, { status }),
  approvals: () => ROUTES.tenantApprovals,
  openExceptions: () => withQuery(ROUTES.tenantExceptions, { status: 'OPEN' }),
  receivables: () => withQuery(financeTabPath('invoices'), { status: 'ISSUED' }),
  overdue: () => withQuery(financeTabPath('invoices'), { overdue: 'true' }),
  receipts: () => financeTabPath('payments'),
  cashCustody: () => financeTabPath('custody'),
  approvedExpenses: () => withQuery(ROUTES.tenantExpenses, { status: 'APPROVED' }),
  cases: (severity?: string) => withQuery(ROUTES.tenantCases, { severity }),
  signals: (severity?: string) => withQuery(ROUTES.tenantCases, { tab: 'signals', severity }),
} as const;

/** Sum of a count map. */
export function total(counts: Readonly<Record<string, number>>): number {
  return Object.values(counts).reduce((sum, n) => sum + n, 0);
}
