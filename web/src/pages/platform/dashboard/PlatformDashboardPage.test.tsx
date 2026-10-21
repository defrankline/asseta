import { screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PERMISSIONS } from '../../../access/permissionCodes';
import type { platformDashboardService } from '../../../api/services/platformDashboardService';
import type { PlatformDashboardDto } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { PlatformDashboardPage } from './PlatformDashboardPage';

const mocks = vi.hoisted(() => ({
  get: vi.fn<typeof platformDashboardService.get>(),
}));
const getDashboard = mocks.get;
vi.mock('../../../api/services/platformDashboardService', () => ({
  platformDashboardService: { get: mocks.get },
}));

const dashboard: PlatformDashboardDto = {
  as_of: '2026-10-21',
  tenants_by_status: { ACTIVE: 3, ONBOARDING: 1 },
  tenants_by_access: { FULL: 3, READ_ONLY: 1 },
  subscriptions_by_status: { ACTIVE: 3, PAST_DUE: 1 },
  churn_events_30d: 2,
  by_currency: [
    {
      currency: 'TZS',
      contracted_mrr: '1500000.0000',
      contracted_arr: '18000000.0000',
      billable_assets: 12,
      enrolled_assets: 10,
      outstanding_balance: '354000.5000',
      open_invoices: 2,
    },
    {
      currency: 'UGX',
      contracted_mrr: '2500000.0000',
      contracted_arr: '30000000.0000',
      billable_assets: 5,
      enrolled_assets: 5,
      outstanding_balance: '125000.5000',
      open_invoices: 1,
    },
  ],
};

describe('PlatformDashboardPage', () => {
  it('renders one card per currency with its own minor units and never a cross-currency total', async () => {
    getDashboard.mockResolvedValue(dashboard);
    renderWithProviders(<PlatformDashboardPage />, {
      permissions: [PERMISSIONS.platformDashboardRead],
    });

    const tzs = await screen.findByRole('region', { name: 'TZS totals' });
    expect(within(tzs).getByText('TZS 1,500,000.00')).toBeInTheDocument();
    expect(within(tzs).getByText('TZS 18,000,000.00')).toBeInTheDocument();
    expect(within(tzs).getByText('TZS 354,000.50')).toBeInTheDocument();
    expect(within(tzs).getByText('12 / 10')).toBeInTheDocument();

    const ugx = screen.getByRole('region', { name: 'UGX totals' });
    expect(within(ugx).getByText('UGX 2,500,000')).toBeInTheDocument();
    expect(within(ugx).getByText('UGX 125,001')).toBeInTheDocument();

    // 1,500,000 + 2,500,000 must never be shown as a combined figure.
    expect(screen.queryByText(/4,000,000/)).not.toBeInTheDocument();
    expect(
      within(screen.getByRole('region', { name: 'Churn events (30 days)' })).getByText('2'),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole('region', { name: 'Tenants by status' })).getByText('4'),
    ).toBeInTheDocument();
  });

  it('shows an error state with retry when loading fails', async () => {
    getDashboard.mockRejectedValue(new Error('boom'));
    renderWithProviders(<PlatformDashboardPage />);
    expect(await screen.findByText('Could not load the dashboard')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  });
});
