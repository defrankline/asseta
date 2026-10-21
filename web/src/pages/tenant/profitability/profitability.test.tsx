import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { profitabilityService } from '../../../api/services/financeService';
import type { ProfitabilityRowDto } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { ProfitabilityPage } from './ProfitabilityPage';

const mocks = vi.hoisted(() => ({ report: vi.fn<typeof profitabilityService.report>() }));
vi.mock('../../../api/services/financeService', () => ({ profitabilityService: mocks }));

const row = (o: Partial<ProfitabilityRowDto>): ProfitabilityRowDto => ({
  group_key: 'aaaaaaaa-0000-4000-8000-000000000001',
  label: 'EX-01 · Excavator',
  currency: 'TZS',
  revenue: '1200000.0000',
  reversed_revenue: '0.0000',
  net_revenue: '1200000.0000',
  expense_cost: '45000.0000',
  fuel_cost: '128000.0000',
  direct_cost: '173000.0000',
  margin: '1027000.0000',
  cost_by_category: { FUEL: '128000.0000', TYRES: '45000.0000' },
  ...o,
});

beforeEach(() => {
  mocks.report.mockImplementation((groupBy, from, to) =>
    Promise.resolve({
      group_by: groupBy,
      period_from: from,
      period_to: to,
      timezone: 'Africa/Dar_es_Salaam',
      rows: [
        row({}),
        row({
          group_key: null,
          label: 'Unattributed',
          revenue: '0.0000',
          net_revenue: '0.0000',
          margin: '-20000.0000',
          expense_cost: '20000.0000',
          fuel_cost: '0.0000',
          direct_cost: '20000.0000',
          cost_by_category: { OFFICE: '20000.0000' },
        }),
        row({ currency: 'USD', revenue: '500.0000', net_revenue: '500.0000', margin: '500.0000' }),
      ],
    }),
  );
});

describe('ProfitabilityPage', () => {
  it('groups rows per currency, shows unattributed costs and categories', async () => {
    renderWithProviders(<ProfitabilityPage />, { tenantPermissions: [P.tenantFinanceReport] });
    const tzs = await screen.findByRole('region', { name: 'Profitability in TZS' });
    const usd = screen.getByRole('region', { name: 'Profitability in USD' });
    expect(within(tzs).getByText('Unattributed (no machine)')).toBeInTheDocument();
    expect(within(tzs).getByText('TZS 1,027,000.00')).toBeInTheDocument();
    expect(within(tzs).getByText('-TZS 20,000.00')).toBeInTheDocument();
    expect(within(tzs).getByText(/OFFICE/)).toBeInTheDocument();
    expect(within(tzs).queryByText(/USD/)).not.toBeInTheDocument();
    expect(within(usd).getAllByText('USD 500.00').length).toBeGreaterThan(0);
    expect(mocks.report).toHaveBeenCalledWith(
      'MACHINE',
      expect.any(String),
      expect.any(String),
      expect.any(AbortSignal),
    );
  });

  it('switches grouping and period', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProfitabilityPage />, { tenantPermissions: [P.tenantFinanceReport] });
    await screen.findByRole('region', { name: 'Profitability in TZS' });
    await user.click(screen.getByRole('button', { name: 'By customer' }));
    await waitFor(() => {
      expect(mocks.report).toHaveBeenLastCalledWith(
        'CUSTOMER',
        expect.any(String),
        expect.any(String),
        expect.any(AbortSignal),
      );
    });
    const from = screen.getByLabelText('From');
    await user.clear(from);
    await user.type(from, '2026-09-01');
    await waitFor(() => {
      expect(mocks.report).toHaveBeenLastCalledWith(
        'CUSTOMER',
        '2026-09-01',
        expect.any(String),
        expect.any(AbortSignal),
      );
    });
  });
});
