import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { tenantService } from '../../../api/services/tenantService';
import type { SubscriptionDto, TenantDto } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { TenantDetailPage } from './TenantDetailPage';

const mocks = vi.hoisted(() => ({
  get: vi.fn<typeof tenantService.get>(),
  getSubscription: vi.fn<typeof tenantService.getSubscription>(),
}));
vi.mock('../../../api/services/tenantService', () => ({
  tenantService: { get: mocks.get, getSubscription: mocks.getSubscription },
}));
// The panel under test is the company record; stand in for the lifecycle panel and ledger tabs.
vi.mock('./SubscriptionPanel', () => ({
  SubscriptionPanel: ({ onChanged }: { onChanged: () => void }) => (
    <button type="button" onClick={onChanged}>
      Simulate transition
    </button>
  ),
}));
vi.mock('./CompanyPanel', () => ({
  CompanyPanel: ({ tenant }: { tenant: TenantDto }) => <p>{tenant.access_state_reason}</p>,
}));
vi.mock('./EnrollmentsTab', () => ({ EnrollmentsTab: () => null }));
vi.mock('./PendingChargesTab', () => ({ PendingChargesTab: () => null }));
vi.mock('./RateVersionsTab', () => ({ RateVersionsTab: () => null }));
vi.mock('./TenantInvoicesTab', () => ({ TenantInvoicesTab: () => null }));

const TENANT_ID = '11111111-1111-4111-8111-111111111111';

describe('TenantDetailPage', () => {
  it('refreshes the company record after a subscription lifecycle change', async () => {
    const tenant = { id: TENANT_ID, display_name: 'Kilimanjaro', legal_name: 'Kilimanjaro Ltd' };
    mocks.get
      .mockResolvedValueOnce({ ...tenant, access_state_reason: 'Onboarding' } as TenantDto)
      .mockResolvedValue({ ...tenant, access_state_reason: 'Subscription active' } as TenantDto);
    mocks.getSubscription.mockResolvedValue({ id: 'sub-1', status: 'ACTIVE' } as SubscriptionDto);
    renderWithProviders(
      <Routes>
        <Route path="/platform/tenants/:tenantId" element={<TenantDetailPage />} />
      </Routes>,
      {
        permissions: [P.platformTenantRead, P.platformSubscriptionRead],
        route: `/platform/tenants/${TENANT_ID}`,
      },
    );
    expect(await screen.findByText('Onboarding')).toBeInTheDocument();
    await userEvent.click(await screen.findByRole('button', { name: 'Simulate transition' }));
    expect(await screen.findByText('Subscription active')).toBeInTheDocument();
    await waitFor(() => {
      expect(mocks.get).toHaveBeenCalledTimes(2);
    });
  });
});
