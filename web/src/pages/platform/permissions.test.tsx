import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../access/permissionCodes';
import type { platformInvoiceService } from '../../api/services/platformInvoiceService';
import type { platformPaymentService } from '../../api/services/platformPaymentService';
import type { tenantService } from '../../api/services/tenantService';
import type { SubscriptionDto } from '../../api/types';
import { makeInvoice, makePayment, SUB_ID } from '../../test/billingFixtures';
import { renderWithProviders } from '../../test/renderWithProviders';
import { InvoiceDetailDialog } from './invoices/InvoiceDetailDialog';
import { PaymentsPage } from './payments/PaymentsPage';
import { SubscriptionPanel } from './tenantDetail/SubscriptionPanel';
import { TenantsPage } from './tenants/TenantsPage';

const mocks = vi.hoisted(() => ({
  listTenants: vi.fn<typeof tenantService.list>(),
  listPayments: vi.fn<typeof platformPaymentService.list>(),
  getInvoice: vi.fn<typeof platformInvoiceService.get>(),
}));
vi.mock('../../api/services/tenantService', () => ({ tenantService: { list: mocks.listTenants } }));
vi.mock('../../api/services/platformPaymentService', () => ({
  platformPaymentService: { list: mocks.listPayments },
}));
vi.mock('../../api/services/platformInvoiceService', () => ({
  platformInvoiceService: { get: mocks.getInvoice },
}));

const emptyPage = { items: [], total: 0, page: 1, page_size: 25 };

const subscription: SubscriptionDto = {
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
  enrolled_assets: 4,
  billable_assets: 5,
  current_rate: null,
};

describe('permission-gated platform actions', () => {
  it('shows "Onboard tenant" only with platform.tenant.create', async () => {
    mocks.listTenants.mockResolvedValue(emptyPage);
    const { unmount } = renderWithProviders(<TenantsPage />, {
      permissions: [P.platformTenantRead],
    });
    expect(await screen.findByText('No tenants yet')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Onboard tenant' })).not.toBeInTheDocument();
    unmount();
    renderWithProviders(<TenantsPage />, {
      permissions: [P.platformTenantRead, P.platformTenantCreate],
    });
    expect(await screen.findByRole('button', { name: 'Onboard tenant' })).toBeInTheDocument();
  });

  it('shows payment Verify/Reject only with platform.payment.manage', async () => {
    mocks.listPayments.mockResolvedValue({
      ...emptyPage,
      items: [makePayment()],
      total: 1,
    });
    const { unmount } = renderWithProviders(<PaymentsPage />, {
      permissions: [P.platformPaymentRead],
    });
    expect(await screen.findByText('CRDB-001')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Verify' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
    unmount();
    renderWithProviders(<PaymentsPage />, {
      permissions: [P.platformPaymentRead, P.platformPaymentManage],
    });
    expect(await screen.findByRole('button', { name: 'Verify' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reject' })).toBeInTheDocument();
  });

  it('hides Record payment / Apply credit without manage permissions', async () => {
    mocks.getInvoice.mockResolvedValue(makeInvoice());
    mocks.listPayments.mockResolvedValue(emptyPage);
    const { unmount } = renderWithProviders(
      <InvoiceDetailDialog invoiceId="x" onClose={vi.fn()} />,
      {
        permissions: [P.platformInvoiceRead, P.platformPaymentRead],
      },
    );
    expect((await screen.findAllByText('TZS 354,000.00')).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'Record payment' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Apply credit' })).not.toBeInTheDocument();
    unmount();
    renderWithProviders(<InvoiceDetailDialog invoiceId="x" onClose={vi.fn()} />, {
      permissions: [P.platformInvoiceRead, P.platformPaymentManage, P.platformCreditManage],
    });
    expect(await screen.findByRole('button', { name: 'Record payment' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Apply credit' })).toBeEnabled();
    expect(await screen.findByText('You cannot view payments.')).toBeInTheDocument();
  });

  it('hides lifecycle actions without platform.subscription.manage', () => {
    const { unmount } = renderWithProviders(
      <SubscriptionPanel subscription={subscription} onChanged={vi.fn()} />,
      { permissions: [P.platformSubscriptionRead] },
    );
    expect(screen.getByText('Subscription AGR-0001')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Change status' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Evaluate entitlement' })).not.toBeInTheDocument();
    unmount();
    renderWithProviders(<SubscriptionPanel subscription={subscription} onChanged={vi.fn()} />, {
      permissions: [P.platformSubscriptionRead, P.platformSubscriptionManage],
    });
    expect(screen.getByRole('button', { name: 'Change status' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Evaluate entitlement' })).toBeInTheDocument();
  });
});
