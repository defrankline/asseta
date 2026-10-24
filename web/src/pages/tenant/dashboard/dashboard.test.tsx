import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { overviewService } from '../../../api/services/overviewService';
import type { TenantOverviewDto } from '../../../api/types';
import { initialFilter, withQuery } from '../../../navigation/urlFilters';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { DashboardPage } from './DashboardPage';
import { freshness } from './dashboardModel';

const mocks = vi.hoisted(() => ({ get: vi.fn<typeof overviewService.get>() }));
vi.mock('../../../api/services/overviewService', () => ({ overviewService: mocks }));

const NOW = Date.now();
const minutesAgo = (m: number) => new Date(NOW - m * 60_000).toISOString();

function overview(overrides: Partial<TenantOverviewDto> = {}): TenantOverviewDto {
  return {
    tenant_id: 't',
    as_of: minutesAgo(0),
    timezone: 'Africa/Dar_es_Salaam',
    fleet: {
      machines: 12,
      connectivity: { live: 5, recent: 2, stale: 1, offline: 3, never: 0, no_tracker: 1 },
      reported_work_state: { WORKING: 4, IDLE: 8 },
      engine_on_verified: 3,
      open_alerts: { info: 1, warning: 2, critical: 4 },
      latest_source_at: minutesAgo(5),
    },
    work: {
      jobs_by_status: { IN_PROGRESS: 2, COMPLETED: 7 },
      pending_approvals: 3,
      readings_needing_review: 1,
      open_exceptions: 2,
      latest_source_at: minutesAgo(30),
    },
    money: {
      month_start: '2026-10-01',
      currencies: [
        {
          currency: 'TZS',
          receivables_outstanding: '1500000.0000',
          receivables_overdue: '250000.0000',
          overdue_invoices: 2,
          verified_receipts_mtd: '400000.0000',
          approved_expenses_mtd: '120000.0000',
          cash_with_supervisors: '80000.0000',
        },
      ],
      latest_source_at: minutesAgo(60),
    },
    risk: {
      open_cases: { info: 0, warning: 1, critical: 2 },
      signals_last_7_days: null,
      latest_source_at: minutesAgo(60),
    },
    ...overrides,
  };
}

function workOf(o: TenantOverviewDto) {
  if (o.work === null) throw new Error('fixture has a work section');
  return o.work;
}

function fleetOf(o: TenantOverviewDto) {
  if (o.fleet === null) throw new Error('fixture has a fleet section');
  return o.fleet;
}

const ALL = [P.tenantFleetRead, P.tenantJobRead, P.tenantFinanceRead, P.tenantCaseRead];

function renderDashboard(data: TenantOverviewDto, perms: string[] = ALL) {
  mocks.get.mockResolvedValue(data);
  renderWithProviders(<DashboardPage />, { tenantPermissions: perms, route: '/tenant/dashboard' });
}

function link(name: RegExp) {
  return screen.getByRole('link', { name });
}

beforeEach(() => {
  mocks.get.mockReset();
});

describe('DashboardPage', () => {
  it('renders only the sections the API returned', async () => {
    renderDashboard(overview({ money: null, risk: null }));
    expect(await screen.findByRole('heading', { name: 'Fleet', level: 2 })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Work', level: 2 })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Money' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Risk' })).not.toBeInTheDocument();
  });

  it('hides counts the caller may not see (null within a section)', async () => {
    renderDashboard(
      overview({
        work: { ...workOf(overview()), pending_approvals: null, readings_needing_review: null },
      }),
    );
    await screen.findByRole('heading', { name: 'Work', level: 2 });
    expect(screen.queryByRole('heading', { name: 'Pending approvals' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Open exceptions' })).toBeInTheDocument();
  });

  it('links fleet and job figures to their filtered lists', async () => {
    renderDashboard(overview());
    await screen.findByRole('heading', { name: 'Fleet', level: 2 });
    expect(link(/^Machines, Offline: 3/)).toHaveAttribute(
      'href',
      '/tenant/fleet?connectivity=OFFLINE',
    );
    expect(link(/^Machines, Never reported: 0/)).toHaveAttribute(
      'href',
      '/tenant/fleet?connectivity=NEVER_REPORTED',
    );
    expect(link(/^Jobs, In progress: 2/)).toHaveAttribute(
      'href',
      '/tenant/jobs?status=IN_PROGRESS',
    );
    expect(link(/^Open alerts, Critical: 4/)).toHaveAttribute(
      'href',
      '/tenant/alerts?status=OPEN&severity=CRITICAL',
    );
    expect(link(/^Pending approvals: 3/)).toHaveAttribute('href', '/tenant/approvals');
  });

  it('links money and risk figures, per currency, and respects page permissions', async () => {
    renderDashboard(overview());
    const money = await screen.findByRole('article', { name: 'TZS' });
    expect(within(money).getByRole('link', { name: /Overdue \(2 invoices\)/ })).toHaveAttribute(
      'href',
      '/tenant/finance?tab=invoices&overdue=true',
    );
    expect(within(money).getByRole('link', { name: /Cash held by supervisors/ })).toHaveAttribute(
      'href',
      '/tenant/finance/cash?tab=custody',
    );
    // No tenant.expense.read: the expenses figure is shown without a link.
    expect(within(money).getByText('Approved expenses this month')).toBeInTheDocument();
    expect(
      within(money).queryByRole('link', { name: /Approved expenses/ }),
    ).not.toBeInTheDocument();
    expect(link(/^Open cases, Critical: 2/)).toHaveAttribute(
      'href',
      '/tenant/cases?severity=CRITICAL',
    );
    expect(screen.queryByRole('heading', { name: /Signals/ })).not.toBeInTheDocument();
  });

  it('flags a section whose newest source data is older than its threshold', async () => {
    renderDashboard(
      overview({ fleet: { ...fleetOf(overview()), latest_source_at: minutesAgo(5 * 60) } }),
    );
    expect(await screen.findByTestId('stale-fleet')).toHaveTextContent(/more than 2 hours/);
    expect(screen.queryByTestId('stale-work')).not.toBeInTheDocument();
    expect(screen.getByText(/As of .* times in Africa\/Dar_es_Salaam/)).toBeInTheDocument();
  });

  it('explains when no section is available for the role', async () => {
    renderDashboard(overview({ fleet: null, work: null, money: null, risk: null }));
    expect(await screen.findByText('Nothing to summarise for your role')).toBeInTheDocument();
  });
});

describe('dashboard helpers', () => {
  it('computes freshness against per-section thresholds', () => {
    expect(freshness(null, NOW, 'fleet')).toEqual({ ageMs: null, stale: false });
    expect(freshness(minutesAgo(90), NOW, 'fleet').stale).toBe(false);
    expect(freshness(minutesAgo(180), NOW, 'fleet').stale).toBe(true);
    expect(freshness(minutesAgo(180), NOW, 'money').stale).toBe(false);
  });

  it('builds deep links and reads only known filter values back', () => {
    expect(withQuery('/tenant/finance?tab=invoices', { status: 'ISSUED', q: '' })).toBe(
      '/tenant/finance?tab=invoices&status=ISSUED',
    );
    const params = new URLSearchParams('status=OPEN&severity=BOGUS');
    expect(initialFilter(params, 'status', ['OPEN', 'RESOLVED'], '')).toBe('OPEN');
    expect(initialFilter(params, 'severity', [{ value: 'CRITICAL' }], 'x')).toBe('x');
    expect(initialFilter(params, 'missing', ['A'], 'A')).toBe('A');
  });
});
