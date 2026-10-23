import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../test/renderWithProviders';
import { MyAccessPage } from './MyAccessPage';

const auth = vi.hoisted(() => ({
  changePassword: vi.fn(),
  clearPasswordChange: vi.fn(),
  passwordChange: null as 'success' | 'cancelled' | 'error' | null,
}));
vi.mock('../auth/useAuth', () => ({ useAuth: () => auth }));

describe('MyAccessPage', () => {
  it('offers a password change through Keycloak and confirms it after the redirect back', async () => {
    auth.passwordChange = 'success';
    renderWithProviders(<MyAccessPage />);
    await userEvent.click(await screen.findByRole('button', { name: 'Change password' }));
    expect(auth.changePassword).toHaveBeenCalledOnce();
    expect(await screen.findByText('Password changed.')).toBeInTheDocument();
    expect(auth.clearPasswordChange).toHaveBeenCalled();
  });
});
