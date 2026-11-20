import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { tenantAccessService } from '../../../api/services/tenantAccessService';
import type { MemberDto } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { roleChanges, splitName } from './accessForm';
import { AccessPage } from './AccessPage';

const mocks = vi.hoisted(() => ({
  listMembers: vi.fn<typeof tenantAccessService.listMembers>(),
  listRoles: vi.fn<typeof tenantAccessService.listRoles>(),
  invite: vi.fn<typeof tenantAccessService.invite>(),
  grantRole: vi.fn<typeof tenantAccessService.grantRole>(),
  revokeRole: vi.fn<typeof tenantAccessService.revokeRole>(),
  rename: vi.fn<typeof tenantAccessService.rename>(),
  deactivate: vi.fn<typeof tenantAccessService.deactivate>(),
  reactivate: vi.fn<typeof tenantAccessService.reactivate>(),
  resetPassword: vi.fn<typeof tenantAccessService.resetPassword>(),
}));
vi.mock('../../../api/services/tenantAccessService', () => ({ tenantAccessService: mocks }));

const ME = '33333333-3333-4333-8333-333333333333';
const MANAGE = ['tenant.access.read', 'tenant.access.manage', 'tenant.access.assign_approvers'];
const approverMessage = 'Only the company owner can give someone a role that approves things.';

const role = (key: string, approves = false, mandate: string | null = null) => ({
  role_key: key,
  since: '2026-01-01T00:00:00Z',
  mandate_reference: mandate,
  carries_approvals: approves,
});

const member = (over: Partial<MemberDto> & Pick<MemberDto, 'user_id' | 'display_name'>) => ({
  email: `${over.user_id}@client.test`,
  status: 'ACTIVE' as const,
  roles: [role('supervisor')],
  ...over,
});

const OWNER = member({ user_id: ME, display_name: 'Frank Kachinga', roles: [role('owner', true)] });
const DAUDI = member({ user_id: 'u-2', display_name: 'Daudi Mollel' });

beforeEach(() => {
  vi.clearAllMocks();
  mocks.listMembers.mockResolvedValue([OWNER, DAUDI]);
  mocks.listRoles.mockResolvedValue([
    { role_key: 'accountant', carries_approvals: false },
    { role_key: 'owner', carries_approvals: true },
    { role_key: 'supervisor', carries_approvals: false },
  ]);
});

const openActions = async (name: string) => {
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: `Actions for ${name}` }));
  return user;
};

describe('Users & roles', () => {
  it('marks roles held under a mandate and offers no actions on them', async () => {
    mocks.listMembers.mockResolvedValue([
      OWNER,
      member({
        user_id: 'u-3',
        display_name: 'Amina Staff',
        roles: [role('dispatcher', false, 'MSM-2026-0007')],
      }),
    ]);
    renderWithProviders(<AccessPage />, { tenantPermissions: MANAGE });
    const staffRow = (await screen.findByText('Amina Staff')).closest('tr');
    if (staffRow === null) throw new Error('row not found');
    expect(within(staffRow).getByText('Managed service · MSM-2026-0007')).toBeInTheDocument();
    expect(within(staffRow).queryByRole('button', { name: /Actions/ })).not.toBeInTheDocument();
    expect(screen.queryByText(approverMessage)).not.toBeInTheDocument();
  });

  it('never offers deactivate or reset on your own account', async () => {
    renderWithProviders(<AccessPage />, { tenantPermissions: MANAGE });
    const user = await openActions('Frank Kachinga');
    expect(screen.getByRole('menuitem', { name: 'Edit' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Deactivate' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Reset password' })).not.toBeInTheDocument();
    await user.keyboard('{Escape}');
  });

  it('adds a user and shows the one-time password once', async () => {
    mocks.invite.mockResolvedValue({
      user_id: 'u-9',
      created_account: true,
      temporary_password: 'Temp-Pass-123',
    });
    const user = userEvent.setup();
    renderWithProviders(<AccessPage />, { tenantPermissions: MANAGE });
    await user.click(await screen.findByRole('button', { name: 'Add user' }));
    await user.type(screen.getByRole('textbox', { name: /First name/ }), 'Neema');
    await user.type(screen.getByRole('textbox', { name: /Last name/ }), 'Joseph');
    await user.type(screen.getByRole('textbox', { name: /Email/ }), 'Neema@Client.test');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('combobox', { name: /Role/ }));
    await user.click(await screen.findByRole('option', { name: 'Supervisor' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(await screen.findByRole('button', { name: 'Add user' }));
    await waitFor(() => {
      expect(mocks.invite).toHaveBeenCalled();
    });
    expect(mocks.invite.mock.calls[0]?.[0]).toEqual({
      first_name: 'Neema',
      last_name: 'Joseph',
      email: 'neema@client.test',
      role_key: 'supervisor',
    });
    expect(await screen.findByText('Temp-Pass-123')).toBeInTheDocument();
    expect(screen.getByText(/It is shown only now/)).toBeInTheDocument();
  });

  it('deactivates after a confirmation; reactivates without one', async () => {
    mocks.deactivate.mockResolvedValue([]);
    mocks.reactivate.mockResolvedValue([]);
    renderWithProviders(<AccessPage />, { tenantPermissions: MANAGE });
    const user = await openActions('Daudi Mollel');
    await user.click(screen.getByRole('menuitem', { name: 'Deactivate' }));
    expect(screen.getByText(/records stay/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    await waitFor(() => {
      expect(mocks.deactivate).toHaveBeenCalledWith('u-2', expect.any(String));
    });

    mocks.listMembers.mockResolvedValue([
      OWNER,
      { ...DAUDI, status: 'INACTIVE', deactivated_at: '2026-11-20T10:00:00Z' },
    ]);
    await user.click(screen.getByRole('switch', { name: 'Show inactive' }));
    await waitFor(() => {
      expect(mocks.listMembers).toHaveBeenLastCalledWith('ALL', expect.anything());
    });
    expect(await screen.findByText('Inactive')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Actions for Daudi Mollel' }));
    expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('menuitem', { name: 'Reactivate' }));
    await waitFor(() => {
      expect(mocks.reactivate).toHaveBeenCalledWith('u-2', expect.any(String));
    });
  });

  it('resets a password and shows the new one-time password', async () => {
    mocks.resetPassword.mockResolvedValue({ temporary_password: 'New-Temp-456' });
    renderWithProviders(<AccessPage />, { tenantPermissions: MANAGE });
    const user = await openActions('Daudi Mollel');
    await user.click(screen.getByRole('menuitem', { name: 'Reset password' }));
    expect(screen.getByText(/signed out of the apps and the website/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reset password' }));
    expect(await screen.findByText('New-Temp-456')).toBeInTheDocument();
  });

  it('edits the name and roles, saving only what changed', async () => {
    mocks.rename.mockResolvedValue([]);
    mocks.grantRole.mockResolvedValue([]);
    renderWithProviders(<AccessPage />, {
      tenantPermissions: ['tenant.access.read', 'tenant.access.manage'],
    });
    expect(await screen.findByText(approverMessage)).toBeInTheDocument();
    const user = await openActions('Daudi Mollel');
    await user.click(screen.getByRole('menuitem', { name: 'Edit' }));
    expect(screen.getByRole('textbox', { name: /First name/ })).toHaveValue('Daudi');
    // A role that approves things needs the approver-assignment right.
    expect(screen.getByRole('checkbox', { name: 'Owner' })).toBeDisabled();
    await user.click(screen.getByRole('checkbox', { name: 'Accountant' }));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => {
      expect(mocks.grantRole).toHaveBeenCalledWith('u-2', 'accountant', expect.any(String));
    });
    expect(mocks.rename).not.toHaveBeenCalled();
    expect(mocks.revokeRole).not.toHaveBeenCalled();
  });
});

describe('Users & roles form helpers', () => {
  it('splits a name on its last word', () => {
    expect(splitName('Daudi Mollel')).toEqual({ first_name: 'Daudi', last_name: 'Mollel' });
    expect(splitName('Mary Anne  Mushi')).toEqual({ first_name: 'Mary Anne', last_name: 'Mushi' });
    expect(splitName('Juma')).toEqual({ first_name: 'Juma', last_name: '' });
  });

  it('works out the roles to give and to take away', () => {
    expect(roleChanges(DAUDI, ['accountant'])).toEqual({
      grant: ['accountant'],
      revoke: ['supervisor'],
    });
  });
});
