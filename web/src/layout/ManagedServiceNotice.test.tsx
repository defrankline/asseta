import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { managedServiceService } from '../api/services/managedServiceService';
import { BADGE, makeMandateDetail } from '../test/mandateFixtures';
import { renderWithProviders } from '../test/renderWithProviders';
import { ManagedServiceNotice } from './ManagedServiceNotice';

const mocks = vi.hoisted(() => ({ get: vi.fn<typeof managedServiceService.get>() }));
vi.mock('../api/services/managedServiceService', () => ({ managedServiceService: mocks }));

const READ = ['tenant.managed_service.read'];

describe('ManagedServiceNotice', () => {
  it('tells client admins about an in-force mandate and links to review it', async () => {
    mocks.get.mockResolvedValue({ mandate: makeMandateDetail(), recent_actions: [] });
    renderWithProviders(<ManagedServiceNotice />, { tenantPermissions: READ });
    expect(await screen.findByText(/Asseta manages this account under mandate/)).toHaveTextContent(
      'Asseta manages this account under mandate MSM-2026-0007 (consent LTR-889).',
    );
    expect(screen.getByRole('link', { name: 'Review or revoke' })).toHaveAttribute(
      'href',
      '/tenant/managed-service',
    );
  });

  it('stays hidden for ended mandates, failures and staff acting under the mandate', async () => {
    mocks.get.mockResolvedValue({
      mandate: makeMandateDetail({ status: 'REVOKED' }),
      recent_actions: [],
    });
    const { unmount } = renderWithProviders(<ManagedServiceNotice />, { tenantPermissions: READ });
    await vi.waitFor(() => {
      expect(mocks.get).toHaveBeenCalled();
    });
    expect(screen.queryByText(/Asseta manages/)).not.toBeInTheDocument();
    unmount();

    mocks.get.mockRejectedValue(new Error('boom'));
    renderWithProviders(<ManagedServiceNotice />, { tenantPermissions: READ });
    expect(screen.queryByText(/Asseta manages/)).not.toBeInTheDocument();

    mocks.get.mockClear();
    renderWithProviders(<ManagedServiceNotice />, { tenantPermissions: READ, mandate: BADGE });
    expect(mocks.get).not.toHaveBeenCalled();
  });
});
