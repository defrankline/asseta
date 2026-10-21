import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AuthContext, type AuthContextValue } from '../../auth/AuthContext';
import { appConfig } from '../../config/env';
import { LandingPage } from './LandingPage';

function renderLanding(login = vi.fn()) {
  const auth: AuthContextValue = {
    status: 'unauthenticated',
    subject: null,
    username: null,
    error: null,
    login,
    logout: vi.fn(),
    getAccessToken: () => Promise.resolve(null),
    refreshToken: () => Promise.resolve(),
  };
  render(
    <AuthContext.Provider value={auth}>
      <LandingPage />
    </AuthContext.Provider>,
  );
  return login;
}

describe('LandingPage', () => {
  it('presents Asseta and starts sign-in from the header and hero', async () => {
    const login = renderLanding();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/where every machine is/i);
    expect(screen.getByRole('heading', { name: 'Live fleet map' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    await userEvent.click(screen.getByRole('button', { name: 'Sign in to your console' }));
    expect(login).toHaveBeenCalledTimes(2);
  });

  it('hides "Request a demo" until a contact email is configured', () => {
    expect(appConfig.contactEmail).toBeNull();
    renderLanding();
    expect(screen.queryByRole('link', { name: 'Request a demo' })).not.toBeInTheDocument();
  });
});
