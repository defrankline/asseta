import { act, render, screen, waitFor } from '@testing-library/react';
import { useEffect } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { requestContext } from '../api/requestContext';
import { useAuth } from './useAuth';
import { AuthProvider } from './AuthProvider';
import type { AuthClient } from './keycloak';

function Status() {
  const { status } = useAuth();
  return <span data-testid="status">{status}</span>;
}

function hangingClient(): AuthClient {
  return {
    authenticated: false,
    init: () => new Promise<boolean>(() => undefined), // silent check-sso never reports back
    login: vi.fn(() => Promise.resolve()),
    logout: vi.fn(() => Promise.resolve()),
    updateToken: vi.fn(() => Promise.resolve(true)),
  };
}

describe('AuthProvider silent SSO', () => {
  it('falls back to unauthenticated instead of hanging when check-sso never completes', async () => {
    render(
      <AuthProvider client={hangingClient()} silentSsoTimeoutMs={50}>
        <Status />
      </AuthProvider>,
    );
    expect(screen.getByTestId('status').textContent).toBe('initializing');
    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('unauthenticated');
    });
  });
});

describe('AuthProvider forced refresh', () => {
  function signedInClient() {
    const updateToken = vi.fn<(minValidity: number) => Promise<boolean>>(() =>
      Promise.resolve(true),
    );
    const login = vi.fn(() => Promise.resolve());
    const client: AuthClient = {
      authenticated: true,
      token: 'tok',
      init: () => Promise.resolve(true),
      login,
      logout: vi.fn(() => Promise.resolve()),
      updateToken,
    };
    return { client, updateToken, login };
  }

  function Refresh() {
    const { status, refreshToken } = useAuth();
    return (
      <button
        type="button"
        onClick={() => {
          void refreshToken();
        }}
      >
        {status}
      </button>
    );
  }

  it('refreshes unconditionally (updateToken(-1)) via the hook and the request context', async () => {
    const { client, updateToken } = signedInClient();
    render(
      <AuthProvider client={client}>
        <Refresh />
      </AuthProvider>,
    );
    const button = await screen.findByRole('button', { name: 'authenticated' });
    act(() => {
      button.click();
    });
    await waitFor(() => {
      expect(updateToken).toHaveBeenLastCalledWith(-1);
    });
    updateToken.mockClear();
    await requestContext.refreshAccessToken();
    expect(updateToken).toHaveBeenCalledWith(-1);
  });

  it('rejects and starts interactive login when the forced refresh fails', async () => {
    const { client, updateToken, login } = signedInClient();
    updateToken.mockRejectedValue(new Error('refresh token expired'));
    render(
      <AuthProvider client={client}>
        <Status />
      </AuthProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('authenticated');
    });
    await expect(requestContext.refreshAccessToken()).rejects.toThrow('refresh token expired');
    expect(login).toHaveBeenCalled();
  });

  it('notifies token-refresh subscribers after keycloak reports a successful refresh', async () => {
    const { client } = signedInClient();
    const listener = vi.fn();
    function Subscriber() {
      const { subscribeTokenRefresh } = useAuth();
      useEffect(() => subscribeTokenRefresh(listener), [subscribeTokenRefresh]);
      return null;
    }
    const view = render(
      <AuthProvider client={client}>
        <Subscriber />
        <Status />
      </AuthProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('authenticated');
    });
    act(() => {
      client.onAuthRefreshSuccess?.();
    });
    expect(listener).toHaveBeenCalledTimes(1);
    view.unmount();
    client.onAuthRefreshSuccess?.();
    expect(listener).toHaveBeenCalledTimes(1);
  });
});
