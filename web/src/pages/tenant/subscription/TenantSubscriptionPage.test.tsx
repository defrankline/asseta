import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { tenantBillingService } from '../../../api/services/tenantBillingService';
import { makeInvoice, SUB_ID } from '../../../test/billingFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { TenantSubscriptionPage } from './TenantSubscriptionPage';

const mocks = vi.hoisted(() => ({
  subscription: vi.fn<typeof tenantBillingService.subscription>(),
  invoices: vi.fn<typeof tenantBillingService.invoices>(),
}));
vi.mock('../../../api/services/tenantBillingService', () => ({ tenantBillingService: mocks }));

describe('TenantSubscriptionPage', () => {
  it('shows the subscription read-only and opens an invoice', async () => {
    const user = userEvent.setup();
    mocks.subscription.mockResolvedValue({
      id: SUB_ID,
      tenant_id: '11111111-1111-4111-8111-111111111111',
      agreement_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
      agreement_number: 'AGR-0001',
      status: 'ACTIVE',
      start_date: '2026-09-01',
      billing_start_date: '2026-09-01',
      billing_anchor_day: 1,
      payment_terms_days: 14,
      current_period_start: '2026-10-01',
      current_period_end: '2026-10-31',
      cancellation_effective_date: null,
      manually_suspended: false,
      enrolled_assets: 3,
      billable_assets: 3,
      current_rate: null,
    });
    mocks.invoices.mockResolvedValue([makeInvoice()]);
    renderWithProviders(<TenantSubscriptionPage />, { tenantPermissions: ['tenant.billing.read'] });
    expect(await screen.findByText('Agreement AGR-0001')).toBeInTheDocument();
    expect(await screen.findByText('INV-2026-0001')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'View' }));
    expect(await screen.findByText('Invoice INV-2026-0001')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Record payment|Apply credit/ })).toBeNull();
  });
});
