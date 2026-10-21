import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { customerService } from '../../../api/services/customerService';
import type { jobService } from '../../../api/services/jobService';
import type { machineService } from '../../../api/services/machineService';
import type { RateCardDto } from '../../../api/types';
import { makeJob } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { CustomersPage } from '../customers/CustomersPage';
import { JobsPage } from './JobsPage';
import { ACTIVE_RECORD } from '../../../test/lifecycleFixtures';

const mocks = vi.hoisted(() => ({
  listJobs: vi.fn<typeof jobService.list>(),
  listCustomers: vi.fn<typeof customerService.list>(),
  listRateCards: vi.fn<typeof customerService.listRateCards>(),
  listMachines: vi.fn<typeof machineService.list>(),
  listCategories: vi.fn<typeof machineService.listCategories>(),
}));
vi.mock('../../../api/services/jobService', () => ({ jobService: { list: mocks.listJobs } }));
vi.mock('../../../api/services/customerService', () => ({
  customerService: { list: mocks.listCustomers, listRateCards: mocks.listRateCards },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: { list: mocks.listMachines, listCategories: mocks.listCategories },
}));

beforeEach(() => {
  mocks.listJobs.mockResolvedValue({ items: [makeJob()], total: 1, page: 1, page_size: 25 });
  mocks.listCustomers.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
  mocks.listMachines.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 });
  mocks.listCategories.mockResolvedValue([
    { id: CATEGORY, name: 'Excavators', description: null, ...ACTIVE_RECORD },
  ]);
  mocks.listRateCards.mockResolvedValue([
    rateCard('rc-old', '2026-01-01T00:00:00Z', '120000.0000'),
    rateCard('rc-now', '2026-06-01T00:00:00Z', '150000.0000'),
    rateCard('rc-next', '2999-01-01T00:00:00Z', '170000.0000'),
  ]);
});

const CATEGORY = 'cccccccc-1111-4111-8111-111111111111';
function rateCard(id: string, from: string, rate: string): RateCardDto {
  return {
    id,
    machine_category_id: CATEGORY,
    effective_from: from,
    hourly_rate: rate,
    minimum_hours: '8.0000',
    currency: 'TZS',
    reason: `Price ${id}`,
  };
}

describe('Gate 3 page gating', () => {
  it('lists jobs and hides New job without tenant.job.write', async () => {
    renderWithProviders(<JobsPage />, { tenantPermissions: ['tenant.job.read'] });
    expect(await screen.findByText('J-100')).toBeInTheDocument();
    expect(screen.getByText('Negotiated rate')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New job' })).not.toBeInTheDocument();
  });

  it('offers New job with write permission unless the tenant is read-only', async () => {
    const perms = ['tenant.job.read', 'tenant.job.write'];
    const { unmount } = renderWithProviders(<JobsPage />, { tenantPermissions: perms });
    expect(await screen.findByRole('button', { name: 'New job' })).toBeInTheDocument();
    unmount();
    renderWithProviders(<JobsPage />, { tenantPermissions: perms, accessState: 'READ_ONLY' });
    await screen.findByText('J-100');
    expect(screen.queryByRole('button', { name: 'New job' })).not.toBeInTheDocument();
  });

  it('shows the rate-card version history to readers; actions need tenant.customer.write', async () => {
    const perms = ['tenant.customer.read', 'tenant.machine.read'];
    const { unmount } = renderWithProviders(<CustomersPage />, { tenantPermissions: perms });
    const table = await screen.findByRole('table', { name: 'Rate-card versions · Excavators' });
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((r) => r.textContent)).toEqual([
      expect.stringMatching(/^Scheduled.*170,000\.00.*Price rc-next/),
      expect.stringMatching(/^In force.*150,000\.00.*Price rc-now/),
      expect.stringMatching(/^Superseded.*120,000\.00.*Price rc-old/),
    ]);
    expect(mocks.listRateCards).toHaveBeenCalledWith(undefined, expect.anything());
    expect(screen.queryByRole('button', { name: 'New customer' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New rate-card version' })).not.toBeInTheDocument();
    unmount();
    renderWithProviders(<CustomersPage />, {
      tenantPermissions: [...perms, 'tenant.customer.write'],
    });
    expect(await screen.findByRole('button', { name: 'New customer' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'New rate-card version' })).toBeEnabled();
    expect(screen.getByText(/Saving creates a new rate-card version/)).toBeInTheDocument();
  });
});
