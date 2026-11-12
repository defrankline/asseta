import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../access/permissionCodes';
import type { meService } from '../api/services/meService';
import { apiError } from '../test/closureFixtures';
import { renderWithProviders } from '../test/renderWithProviders';
import {
  DELETE_ACCOUNT_TEXT,
  DeleteAccountSection,
  PLATFORM_ACCOUNT_TEXT,
} from './DeleteAccountSection';

const mocks = vi.hoisted(() => ({
  deleteMyAccount: vi.fn<typeof meService.deleteMyAccount>(),
  logout: vi.fn(),
}));
vi.mock('../api/services/meService', () => ({
  meService: { deleteMyAccount: mocks.deleteMyAccount },
}));
vi.mock('../auth/useAuth', () => ({ useAuth: () => ({ logout: mocks.logout }) }));

beforeEach(() => {
  mocks.deleteMyAccount.mockResolvedValue({
    user_id: '33333333-3333-4333-8333-333333333333',
    display_name: 'Former user 3333',
    deleted_at: '2026-11-12T08:00:00Z',
    companies: ['Tenant A'],
  });
});
afterEach(() => {
  vi.clearAllMocks();
});

async function deleteAccount() {
  await userEvent.type(screen.getByLabelText(/Type DELETE to confirm/), 'DELETE');
  await userEvent.click(screen.getByRole('button', { name: 'Delete my account' }));
  const dialog = await screen.findByRole('dialog');
  await userEvent.click(within(dialog).getByRole('button', { name: 'Delete my account' }));
}

describe('DeleteAccountSection', () => {
  it('explains the deletion and needs DELETE typed', async () => {
    renderWithProviders(<DeleteAccountSection />);
    expect(screen.getByText(DELETE_ACCOUNT_TEXT)).toBeInTheDocument();
    const button = screen.getByRole('button', { name: 'Delete my account' });
    expect(button).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/Type DELETE to confirm/), 'delete');
    expect(button).toBeDisabled();
  });

  it('deletes after the confirm dialog and signs out to the sign-in page with a message', async () => {
    renderWithProviders(<DeleteAccountSection />);
    await deleteAccount();
    expect(mocks.deleteMyAccount).toHaveBeenCalledWith(null, expect.any(String));
    expect(mocks.logout).toHaveBeenCalledWith('/signed-out?reason=account-deleted');
  });

  it('shows the server message for the last owner, with a link to close the company', async () => {
    mocks.deleteMyAccount.mockRejectedValue(
      apiError('LAST_OWNER', 'You are the last owner of Tenant A', 422),
    );
    renderWithProviders(<DeleteAccountSection />, { tenantPermissions: [P.tenantCompanyClose] });
    await deleteAccount();
    expect(await screen.findByText('You are the last owner of Tenant A')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close Tenant A' })).toBeInTheDocument();
    expect(mocks.logout).not.toHaveBeenCalled();
  });

  it('gives no close link to someone who may not close the company', async () => {
    mocks.deleteMyAccount.mockRejectedValue(apiError('LAST_OWNER', 'Last owner', 422));
    renderWithProviders(<DeleteAccountSection />, { tenantPermissions: [] });
    await deleteAccount();
    expect(await screen.findByText('Last owner')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Close / })).not.toBeInTheDocument();
  });

  it('tells platform staff who removes their account', async () => {
    mocks.deleteMyAccount.mockRejectedValue(apiError('PLATFORM_ACCOUNT', 'raw', 422));
    renderWithProviders(<DeleteAccountSection />);
    await deleteAccount();
    expect(await screen.findByText(PLATFORM_ACCOUNT_TEXT)).toBeInTheDocument();
  });
});
