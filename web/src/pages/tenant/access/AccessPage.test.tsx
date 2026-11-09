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

const approverMessage = 'Only the company owner can give someone a role that approves things.';

describe('Users & roles', () => {
  it('marks roles held under a mandate and offers no revoke for them', async () => {
    mocks.listMembers.mockResolvedValue([
      {
        user_id: 'u-1',
        email: 'owner@client.test',
        display_name: 'Client Owner',
        roles: [
          {
            role_key: 'owner',
            since: '2026-01-01T00:00:00Z',
            mandate_reference: null,
            carries_approvals: true,
          },
        ],
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
            carries_approvals: false,
          },
        ],
      },
    ]);
    renderWithProviders(<AccessPage />, {
      tenantPermissions: [
        'tenant.access.read',
        'tenant.access.manage',
        'tenant.access.assign_approvers',
      ],
    });
    const staffRow = (await screen.findByText('Amina Staff')).closest('tr');
    if (staffRow === null) throw new Error('row not found');
    expect(within(staffRow).getByText('Managed service · MSM-2026-0007')).toBeInTheDocument();
    expect(within(staffRow).queryByRole('button', { name: /Revoke/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Revoke owner from Client Owner' })).toBeEnabled();
    expect(screen.queryByText(approverMessage)).not.toBeInTheDocument();
  });

  it('holds back roles that approve from someone who cannot assign them', async () => {
    mocks.listMembers.mockResolvedValue([
      {
        user_id: 'u-1',
        email: 'lead@client.test',
        display_name: 'Shift Lead',
        roles: [
          {
            role_key: 'shift-lead',
            since: '2026-01-01T00:00:00Z',
            mandate_reference: null,
            carries_approvals: true,
          },
          {
            role_key: 'viewer',
            since: '2026-01-01T00:00:00Z',
            mandate_reference: null,
            carries_approvals: false,
          },
        ],
      },
    ]);
    renderWithProviders(<AccessPage />, {
      tenantPermissions: ['tenant.access.read', 'tenant.access.manage'],
    });
    expect(
      await screen.findByRole('button', { name: 'Revoke shift-lead from Shift Lead' }),
    ).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Revoke viewer from Shift Lead' })).toBeEnabled();
    expect(screen.getByText(approverMessage)).toBeInTheDocument();
  });
});
