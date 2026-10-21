import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { managedServiceService } from '../../../api/services/managedServiceService';
import { BADGE, MANDATE_ID, makeMandateDetail } from '../../../test/mandateFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { ClientManagedServicePage } from './ClientManagedServicePage';

const mocks = vi.hoisted(() => ({
  get: vi.fn<typeof managedServiceService.get>(),
  revoke: vi.fn<typeof managedServiceService.revoke>(),
}));
vi.mock('../../../api/services/managedServiceService', () => ({ managedServiceService: mocks }));

const ADMIN = ['tenant.managed_service.read', 'tenant.managed_service.revoke'];
const ACTIONS = [
  {
    occurred_at: '2026-10-20T10:00:00Z',
    actor: 'amina@asseta.test',
    action: 'job.approved',
    entity_type: 'job',
    entity_id: 'JOB-12',
  },
];

beforeEach(() => {
  mocks.get.mockResolvedValue({ mandate: makeMandateDetail(), recent_actions: ACTIONS });
});

describe('ClientManagedServicePage', () => {
  it('shows an empty state when there is no mandate', async () => {
    mocks.get.mockResolvedValue({ mandate: null, recent_actions: [] });
    renderWithProviders(<ClientManagedServicePage />, { tenantPermissions: ADMIN });
    expect(await screen.findByText('No managed-service mandate')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Revoke mandate' })).not.toBeInTheDocument();
  });

  it('shows terms, staff with access and recent actions', async () => {
    renderWithProviders(<ClientManagedServicePage />, { tenantPermissions: ADMIN });
    expect(await screen.findByText('LTR-889')).toBeInTheDocument();
    expect(screen.getByText('Amina Staff')).toBeInTheDocument();
    expect(screen.getByText('job.approved')).toBeInTheDocument();
    expect(screen.getByText('Job · JOB-12')).toBeInTheDocument();
  });

  it('requires a reason to revoke and sends the version', async () => {
    const user = userEvent.setup();
    mocks.revoke.mockResolvedValue({
      mandate: makeMandateDetail({ status: 'REVOKED', version: 4 }),
      recent_actions: ACTIONS,
    });
    renderWithProviders(<ClientManagedServicePage />, { tenantPermissions: ADMIN });
    await user.click(await screen.findByRole('button', { name: 'Revoke mandate' }));
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    expect(mocks.revoke).not.toHaveBeenCalled();

    await user.type(
      screen.getByRole('textbox', { name: /Reason for revoking/ }),
      'No longer needed',
    );
    await user.click(screen.getByRole('button', { name: 'Revoke mandate' }));
    await waitFor(() => {
      expect(mocks.revoke).toHaveBeenCalledWith(
        MANDATE_ID,
        { version: 3, reason: 'No longer needed' },
        expect.any(String),
      );
    });
    expect(await screen.findByText('Revoked')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Revoke mandate' })).not.toBeInTheDocument();
  });

  it('hides the revoke control while the session acts under the mandate', async () => {
    renderWithProviders(<ClientManagedServicePage />, { tenantPermissions: ADMIN, mandate: BADGE });
    expect(await screen.findByText('LTR-889')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Revoke mandate' })).not.toBeInTheDocument();
  });

  it('hides the revoke control without tenant.managed_service.revoke', async () => {
    renderWithProviders(<ClientManagedServicePage />, {
      tenantPermissions: ['tenant.managed_service.read'],
    });
    expect(await screen.findByText('LTR-889')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Revoke mandate' })).not.toBeInTheDocument();
  });
});
