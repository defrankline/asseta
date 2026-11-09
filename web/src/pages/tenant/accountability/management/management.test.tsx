import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes, useLocation } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../../access/permissionCodes';
import type { accountabilityService } from '../../../../api/services/accountabilityService';
import type {
  AccountabilitySummaryDto,
  EmployeeAccountabilityDto,
  HoursFigureDto,
  MoneyFigureDto,
} from '../../../../api/custodyTypes';
import { TransactionLookup } from '../../../../layout/TransactionLookup';
import { page } from '../../../../test/financeFixtures';
import { renderWithProviders } from '../../../../test/renderWithProviders';
import { LookupResultsPage } from '../../lookup/LookupResultsPage';
import { AccountabilityPage } from '../AccountabilityPage';
import { EmployeeAccountabilityPage } from '../EmployeeAccountabilityPage';
import { PendingAdjustmentsPage } from '../PendingAdjustmentsPage';

const m = vi.hoisted(() => ({
  summary: vi.fn<typeof accountabilityService.summary>(),
  pendingAdjustments: vi.fn<typeof accountabilityService.pendingAdjustments>(),
  employee: vi.fn<typeof accountabilityService.employee>(),
  lookup: vi.fn<typeof accountabilityService.lookup>(),
}));
vi.mock('../../../../api/services/accountabilityService', () => ({ accountabilityService: m }));

const STAFF = '00000000-0000-4000-8000-00000000000a';
const hours = (h: string, route: string): HoursFigureDto => ({ hours: h, count: 2, route });
const money = (amount: string, route: string): MoneyFigureDto => ({
  lines: [{ currency: 'TZS', count: 1, amount }],
  count: 1,
  route,
});
const queue = (route: string) => ({ count: 0, hours: '0', amounts: [], route, items: [] });
const count = (n: number, route: string) => ({ count: n, route });

function summary(): AccountabilitySummaryDto {
  const none = '/tenant/x';
  return {
    as_of: '2026-11-09T08:00:00Z',
    policy_version: 'v1',
    hidden_tiles: [],
    unavailable_tiles: [],
    customer_hours: null,
    hours_awaiting_activation: null,
    engine_hours: null,
    unexplained_hours: null,
    missing_daily_reports: null,
    investigations: null,
    cash: null,
    payments: null,
    discrepancies: null,
    unauthorized_attempts: null,
    outstanding_approvals: null,
    hours_section: {
      purchased: hours('120', '/tenant/hours/purchases?cancelled=false'),
      purchased_value: money('600000', '/tenant/hours/purchases?cancelled=false'),
      activated: hours('100', '/tenant/hours/ledger?entry_type=ACTIVATED'),
      consumed: hours('40', '/tenant/hours/ledger?entry_type=CONSUMED'),
      remaining: hours('60', '/tenant/hours/balances'),
      remaining_by_customer: [
        {
          customer_id: 'c1',
          customer_name: 'Kilimo Co',
          remaining: '60',
          activated: '100',
          consumed: '40',
          route: '/tenant/hours/balances?customer_id=c1',
        },
      ],
      remaining_customers_total: 1,
      unpaid_purchases: queue('/tenant/hours/purchases?queue=UNPAID'),
      unconfirmed_purchases: queue('/tenant/hours/purchases?queue=UNCONFIRMED'),
      awaiting_activation: queue('/tenant/hours/purchases?queue=AWAITING_ACTIVATION'),
    },
    operations_section: {
      operating_hours: hours('50', '/tenant/work-allocations'),
      customer_hours: hours('30', '/tenant/work-allocations?kind=CUSTOMER_WORK'),
      authorized_non_customer_hours: hours(
        '15',
        '/tenant/work-allocations?kind=AUTHORIZED_ACTIVITY',
      ),
      unexplained_hours: hours('5', '/tenant/work-allocations?kind=UNEXPLAINED'),
      by_excavator: [],
      meter_discrepancies: { count: 0, by_type: [], route: '/tenant/exceptions?status=OPEN' },
      pending_reports: count(1, '/tenant/daily-reports?status=SUBMITTED'),
      returned_reports: count(0, '/tenant/daily-reports?status=RETURNED'),
    },
    cash_section: {
      collected: money('5000', '/tenant/customer-payments?method=CASH'),
      held_by_employee: [
        {
          staff_member_id: STAFF,
          staff_member_name: 'Sam Supervisor',
          currency: 'TZS',
          outstanding: '2000',
          in_transit_out: '0',
          claimed_unverified_handovers: '0',
          pending_floats: '0',
          approved_retention: '0',
          route: `/tenant/staff/${STAFF}/accountability`,
        },
      ],
      transferred: money('1', none),
      in_transit: money('1', none),
      declared_for_remittance: money('1', none),
      confirmed_by_company: money('1', none),
      outstanding: money('1', none),
      unconfirmed_remittances: money('1', none),
      disputed_remittances: money('1', none),
      disputed_transfers: money('1', none),
    },
    exceptions_section: {
      unexplained_engine_hours: hours('5', '/tenant/work-allocations?kind=UNEXPLAINED'),
      shortages: money('1', '/tenant/finance/cash/variances?direction=SHORTAGE'),
      overages: money('1', '/tenant/finance/cash/variances?direction=OVERAGE'),
      shortages_opened_in_period: { lines: [], count: 0, route: none },
      overages_opened_in_period: { lines: [], count: 0, route: none },
      pending_adjustments: {
        total: 0,
        by_kind: [],
        oldest: [],
        route: '/tenant/accountability/pending-adjustments',
      },
      unauthorized_attempts: {
        since: '2026-11-02T00:00:00Z',
        permission_denied: 1,
        segregation_of_duties: 1,
        route: '/tenant/security-events',
      },
      unconfirmed_payments: money('1', '/tenant/customer-payments?status=CLAIMED'),
      outstanding_approvals: { total: 0, by_kind: [] },
      overdue_reports: {
        missing_daily_reports: count(0, '/tenant/daily-reports'),
        remittances_overdue_today: count(0, '/tenant/finance/cash/remittance-overdue'),
        total: 0,
      },
      unresolved_variances: { total: 0, by_source: [] },
      changeover_jobs_awaiting_approval: { count: 0, oldest_days: null, items: [] },
    },
  };
}

function Where() {
  const { pathname, search } = useLocation();
  return <p>at {`${pathname}${search}`}</p>;
}

const record = (over: Partial<EmployeeAccountabilityDto['collections'][number]> = {}) => ({
  record_type: 'customer_payment',
  id: 'p1',
  reference: 'COL-2026-000001',
  status: 'CLAIMED',
  occurred_at: '2026-11-05T09:00:00Z',
  amount: '2000',
  unit: 'MONEY',
  currency: 'TZS',
  label: 'COLLECTIONS',
  route: '/tenant/customer-payments/p1',
  ...over,
});

function employee(over: Partial<EmployeeAccountabilityDto> = {}): EmployeeAccountabilityDto {
  return {
    date_from: '2026-10-11',
    date_to: '2026-11-09',
    identity: {
      staff_member_id: STAFF,
      full_name: 'Sam Supervisor',
      employee_code: 'E-1',
      kind: 'SUPERVISOR',
      phone: null,
      is_active: true,
      login_email: 'sam@example.test',
      user_id: null,
      roles: ['supervisor'],
    },
    cash_held: [],
    collections: [record()],
    floats: [],
    transfers_in: [],
    transfers_out: [],
    remittances: [
      record({ id: 'h1', reference: 'RMT-1', route: '/tenant/finance/cash/remittances/h1' }),
    ],
    spending: [],
    retentions: [],
    differences: [],
    custody_adjustments: [],
    reports_submitted: [],
    approvals_made: [],
    adjustments_requested: [],
    adjustments_decided: [],
    scorecard_items: [],
    scorecard_visible: false,
    truncated: [],
    ...over,
  };
}

beforeEach(() => {
  Object.values(m).forEach((f) => f.mockReset());
});

describe('management dashboard', () => {
  it('shows the four groups and links each figure to its filtered list', async () => {
    m.summary.mockResolvedValue(summary());
    renderWithProviders(<AccountabilityPage />, {
      tenantPermissions: [P.tenantAccountabilityRead],
    });
    for (const name of [
      'Customer hours',
      'Excavator operations',
      'Cash accountability',
      'Exceptions and investigations',
    ]) {
      expect(await screen.findByRole('heading', { name, level: 2 })).toBeInTheDocument();
    }
    expect(screen.getByRole('link', { name: /Total hours purchased: 120/ })).toHaveAttribute(
      'href',
      '/tenant/hours/purchases?cancelled=false',
    );
    expect(screen.getByRole('link', { name: /Cash shortages/ })).toHaveAttribute(
      'href',
      '/tenant/finance/cash/variances?direction=SHORTAGE',
    );
    expect(screen.getByRole('link', { name: 'Sam Supervisor' })).toHaveAttribute(
      'href',
      `/tenant/staff/${STAFF}/accountability`,
    );
    expect(screen.getByRole('link', { name: 'Kilimo Co' })).toHaveAttribute(
      'href',
      '/tenant/hours/balances?customer_id=c1',
    );
  });

  it('asks for the chosen period', async () => {
    m.summary.mockResolvedValue(summary());
    renderWithProviders(<AccountabilityPage />, {
      tenantPermissions: [P.tenantAccountabilityRead],
      route: '/?date_from=2026-11-01&date_to=2026-11-09',
    });
    await screen.findByRole('heading', { name: 'Customer hours', level: 2 });
    expect(m.summary).toHaveBeenCalledWith(expect.anything(), {
      date_from: '2026-11-01',
      date_to: '2026-11-09',
    });
  });
});

describe('employee accountability', () => {
  const open = () =>
    renderWithProviders(
      <Routes>
        <Route
          path="/tenant/staff/:staffId/accountability"
          element={<EmployeeAccountabilityPage />}
        />
      </Routes>,
      {
        tenantPermissions: [P.tenantAccountabilityEmployeeRead],
        route: `/tenant/staff/${STAFF}/accountability`,
      },
    );

  it('lists the records per tab, each linking to the record', async () => {
    m.employee.mockResolvedValue(employee());
    open();
    expect(await screen.findByRole('link', { name: 'COL-2026-000001' })).toHaveAttribute(
      'href',
      '/tenant/customer-payments/p1',
    );
    await userEvent.click(screen.getByRole('tab', { name: 'Remittances (1)' }));
    expect(screen.getByRole('link', { name: 'RMT-1' })).toHaveAttribute(
      'href',
      '/tenant/finance/cash/remittances/h1',
    );
  });

  it('hides the scorecard tab unless the viewer may see it', async () => {
    m.employee.mockResolvedValue(employee());
    open();
    await screen.findByRole('tab', { name: 'Collections (1)' });
    expect(screen.queryByRole('tab', { name: /Scorecard items/ })).not.toBeInTheDocument();
  });
});

describe('reference lookup', () => {
  it('is offered only with the permission and opens the result list', async () => {
    renderWithProviders(
      <>
        <TransactionLookup />
        <Where />
      </>,
      { tenantPermissions: [P.tenantLookupRead] },
    );
    await userEvent.type(screen.getByRole('textbox', { name: 'Find a reference' }), 'RMT-7{Enter}');
    await waitFor(() => {
      expect(screen.getByText('at /tenant/lookup?reference=RMT-7')).toBeInTheDocument();
    });
  });

  it('is hidden without the permission', () => {
    renderWithProviders(<TransactionLookup />, { tenantPermissions: [] });
    expect(screen.queryByRole('search')).not.toBeInTheDocument();
  });

  it('shows what happened, when, who and what is left', async () => {
    m.lookup.mockResolvedValue({
      reference: 'HP-1',
      matches: [
        {
          record_type: 'hours_purchase',
          id: 'h1',
          reference: 'HP-1',
          route: '/tenant/hours/purchases/h1',
          status: 'PARTLY_PAID',
          recorded_by: 'u1',
          recorded_by_name: 'Asha Clerk',
          recorded_at: '2026-11-01T08:00:00Z',
          balance_outstanding: '1500',
          balance_unit: 'MONEY',
          currency: 'TZS',
          hours_remaining: '12',
        },
      ],
    });
    renderWithProviders(<LookupResultsPage />, {
      tenantPermissions: [P.tenantLookupRead],
      route: '/?reference=HP-1',
    });
    const card = await screen.findByRole('article', { name: 'HP-1' });
    expect(within(card).getByRole('link', { name: 'HP-1' })).toHaveAttribute(
      'href',
      '/tenant/hours/purchases/h1',
    );
    expect(within(card).getByText('Asha Clerk')).toBeInTheDocument();
    expect(within(card).getByText('Balance outstanding')).toBeInTheDocument();
    expect(within(card).getByText('Hours remaining')).toBeInTheDocument();
  });

  it('says so when nothing matches', async () => {
    m.lookup.mockResolvedValue({ reference: 'NOPE', matches: [] });
    renderWithProviders(<LookupResultsPage />, {
      tenantPermissions: [P.tenantLookupRead],
      route: '/?reference=NOPE',
    });
    expect(await screen.findByText('No record has that reference')).toBeInTheDocument();
  });
});

describe('pending adjustments', () => {
  it('lists waiting records with a link to each', async () => {
    m.pendingAdjustments.mockResolvedValue(
      page([
        {
          kind: 'hours_transfers',
          record_type: 'hours_transfer',
          id: 't1',
          reference: 'HTR-2026-000001',
          status: 'PENDING',
          requested_by: 'u1',
          requested_by_name: 'Asha Clerk',
          requested_at: '2026-11-01T08:00:00Z',
          amount: '4',
          unit: 'HOURS',
          currency: null,
          customer_id: 'c1',
          customer_name: 'Kilimo Co',
          machine_id: null,
          staff_member_id: null,
          route: '/tenant/hours/transfers/t1',
        },
      ]),
    );
    renderWithProviders(<PendingAdjustmentsPage />, {
      tenantPermissions: [P.tenantAccountabilityRead],
      route: '/?all_approvals=true',
    });
    expect(await screen.findByRole('link', { name: 'HTR-2026-000001' })).toHaveAttribute(
      'href',
      '/tenant/hours/transfers/t1',
    );
    expect(m.pendingAdjustments.mock.calls[0]?.[0].filters).toMatchObject({
      all_approvals: 'true',
    });
  });
});
