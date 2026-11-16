import { screen, within } from '@testing-library/react';
import { Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { profitabilityService } from '../api/services/financeService';
import type { insightsService } from '../api/services/insightsService';
import { ROUTES } from '../navigation/routes';
import { ExpensesPage } from '../pages/tenant/expenses/ExpensesPage';
import { InsightsPage } from '../pages/tenant/insights/InsightsPage';
import { ProfitabilityPage } from '../pages/tenant/profitability/ProfitabilityPage';
import { fieldRouteElements } from '../routes/fieldRoutes';
import { makeInsights } from '../test/mlFixtures';
import { renderWithProviders } from '../test/renderWithProviders';
import { PERMISSIONS as P } from './permissionCodes';

const mocks = vi.hoisted(() => ({
  insights: vi.fn<typeof insightsService.get>(),
  report: vi.fn<typeof profitabilityService.report>(),
}));
vi.mock('../api/services/insightsService', () => ({
  insightsService: { get: mocks.insights, manualOverrides: vi.fn() },
  tenantMlService: { status: vi.fn(), observations: vi.fn() },
}));
vi.mock('../api/services/financeService', () => ({
  profitabilityService: { report: mocks.report },
}));
vi.mock('../pages/tenant/expenses/ExpensesTab', () => ({ ExpensesTab: () => <p>Expense list</p> }));
vi.mock('../pages/tenant/expenses/FuelTab', () => ({ FuelTab: () => <p>Fuel list</p> }));
vi.mock('../routes/lazyPages', () => ({
  FieldReadingsPage: () => null,
  FieldFuelPage: () => <p>Fuel page</p>,
  FieldExpensesPage: () => null,
  FieldCashPage: () => null,
}));

const OFF = { disabledCapabilities: ['FUEL'] };

beforeEach(() => {
  mocks.insights.mockResolvedValue(makeInsights());
  mocks.report.mockResolvedValue({
    group_by: 'MACHINE',
    period_from: '2026-11-01',
    period_to: '2026-11-16',
    timezone: 'Africa/Dar_es_Salaam',
    rows: [
      {
        group_key: 'm1',
        label: 'EX-01',
        currency: 'TZS',
        revenue: '100',
        net_revenue: '100',
        expense_cost: '10',
        fuel_cost: '0',
        direct_cost: '10',
        margin: '90',
        cost_by_category: {},
      },
    ],
  });
});

describe('fuel switched off (FUEL in disabled_capabilities)', () => {
  it('shows Expenses without a fuel tab, and the fuel tab while fuel is on', () => {
    const { unmount } = renderWithProviders(<ExpensesPage />, {
      tenantPermissions: [P.tenantExpenseRead],
      ...OFF,
    });
    expect(screen.getByRole('heading', { name: 'Expenses' })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Fuel events' })).not.toBeInTheDocument();
    expect(screen.getByText('Expense list')).toBeInTheDocument();
    unmount();
    renderWithProviders(<ExpensesPage />, { tenantPermissions: [P.tenantExpenseRead] });
    expect(screen.getByRole('tab', { name: 'Fuel events' })).toBeInTheDocument();
  });

  it('even ?tab=fuel stays on expenses', () => {
    renderWithProviders(<ExpensesPage />, {
      tenantPermissions: [P.tenantExpenseRead],
      route: '/tenant/expenses?tab=fuel',
      ...OFF,
    });
    expect(screen.queryByText('Fuel list')).not.toBeInTheDocument();
  });

  it('hides the fuel efficiency insight', async () => {
    renderWithProviders(<InsightsPage />, { tenantPermissions: [P.tenantFleetRead], ...OFF });
    const tabs = await screen.findByRole('tablist', { name: 'Insights' });
    expect(within(tabs).queryByRole('tab', { name: 'Fuel efficiency' })).not.toBeInTheDocument();
    expect(within(tabs).getByRole('tab', { name: 'Utilisation' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });

  it('drops the fuel column from profitability', async () => {
    renderWithProviders(<ProfitabilityPage />, {
      tenantPermissions: [P.tenantFinanceReport],
      ...OFF,
    });
    const table = await screen.findByRole('table', { name: 'TZS profitability' });
    expect(within(table).queryByRole('columnheader', { name: 'Fuel' })).not.toBeInTheDocument();
    expect(within(table).getByRole('columnheader', { name: 'Expenses' })).toBeInTheDocument();
  });

  it('shows the not-enabled state on a direct link to Field work › Fuel', () => {
    renderWithProviders(<Routes>{fieldRouteElements((_p, page) => page)}</Routes>, {
      tenantPermissions: [P.tenantExpenseWrite],
      route: ROUTES.fieldFuel,
      ...OFF,
    });
    expect(screen.queryByText('Fuel page')).not.toBeInTheDocument();
    expect(screen.getByText(/Fuel/)).toBeInTheDocument();
  });
});
