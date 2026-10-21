import { screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { tenantAccessService } from '../../../api/services/tenantAccessService';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { AccessPage } from './AccessPage';

const mocks = vi.hoisted(() => ({
  listMembers: vi.fn<typeof tenantAccessService.listMembers>(),
  revokeRole: vi.fn<typeof tenantAccessService.revokeRole>(),
}));
vi.mock('../../../api/services/tenantAccessService', () => ({ tenantAccessService: mocks }));

describe('Users & roles', () => {
  it('marks roles held under a mandate and offers no revoke for them', async () => {
    mocks.listMembers.mockResolvedValue([
      {
        user_id: 'u-1',
        email: 'owner@client.test',
        display_name: 'Client Owner',
        roles: [{ role_key: 'owner', since: '2026-01-01T00:00:00Z', mandate_reference: null }],
      },
      {
        user_id: 'u-2',
        email: 'amina@asseta.test',
        display_name: 'Amina Staff',
        roles: [
          {
            role_key: 'dispatcher',
            since: '2026-10-01T00:00:00Z',
            mandate_reference: 'MSM-2026-0007',
          },
        ],
      },
    ]);
    renderWithProviders(<AccessPage />, {
      tenantPermissions: ['tenant.access.read', 'tenant.access.manage'],
    });
    const staffRow = (await screen.findByText('Amina Staff')).closest('tr');
    if (staffRow === null) throw new Error('row not found');
    expect(within(staffRow).getByText('Managed service · MSM-2026-0007')).toBeInTheDocument();
    expect(within(staffRow).queryByRole('button', { name: /Revoke/ })).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Revoke owner from Client Owner' }),
    ).toBeInTheDocument();
  });
});
