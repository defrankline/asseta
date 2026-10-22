import { act, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthContext, type AuthContextValue } from '../auth/AuthContext';
import { SessionContext } from '../session/SessionContext';
import { FakeSocket } from '../test/fakeWebSocket';
import { makeMe, makeSession, TENANT_A } from '../test/fixtures';
import { SessionRealtimeProvider } from './SessionRealtimeProvider';

const sockets: FakeSocket[] = [];

class GlobalFakeSocket extends FakeSocket {
  constructor(url: string, protocols?: string[]) {
    super(url, protocols);
    sockets.push(this);
  }
}

function last(): FakeSocket {
  const s = sockets[sockets.length - 1];
  if (s === undefined) throw new Error('no socket');
  return s;
}

beforeEach(() => {
  sockets.length = 0;
  vi.stubGlobal('WebSocket', GlobalFakeSocket);
});
afterEach(() => {
  vi.unstubAllGlobals();
});

function renderWith(reload = vi.fn(), refreshToken = vi.fn(() => Promise.resolve())) {
  let refreshed: () => void = () => undefined;
  const auth: AuthContextValue = {
    status: 'authenticated',
    subject: 's',
    username: 'u',
    error: null,
    login: vi.fn(),
    logout: vi.fn(),
    getAccessToken: () => Promise.resolve('jwt-1'),
    refreshToken,
    subscribeTokenRefresh: (l) => {
      refreshed = l;
      return () => undefined;
    },
  };
  const session = {
    ...makeSession(makeMe(), { kind: 'tenant', tenantId: TENANT_A }),
    reload,
  };
  render(
    <AuthContext.Provider value={auth}>
      <SessionContext.Provider value={session}>
        <SessionRealtimeProvider>
          <p>app</p>
        </SessionRealtimeProvider>
      </SessionContext.Provider>
    </AuthContext.Provider>,
  );
  return {
    reload,
    refreshToken,
    refreshed: () => {
      refreshed();
    },
  };
}

const flush = () => act(() => new Promise((r) => setTimeout(r, 0)));

describe('SessionRealtimeProvider', () => {
  it('connects to /api/v1/ws for the active tenant with the token in the first message', async () => {
    renderWith();
    await flush();
    const s = last();
    expect(s.url).toMatch(/^ws:\/\/[^/]+\/api\/v1\/ws$/);
    expect(s.url).not.toContain('jwt-1');
    act(() => {
      s.open();
    });
    expect(s.sentMessages()[0]).toEqual({ type: 'auth', token: 'jwt-1', tenant_id: TENANT_A });
  });

  it('forces a token refresh on reauth_required / 4401 and re-reads /me on 4403', async () => {
    const { reload, refreshToken, refreshed } = renderWith();
    await flush();
    act(() => {
      last().accept();
      last().receive({ type: 'reauth_required', payload: { expires_at: 1 } });
    });
    expect(refreshToken).toHaveBeenCalledTimes(1);
    act(() => {
      refreshed(); // keycloak reported the refresh: the new token goes on the open socket
    });
    await flush();
    expect(
      last()
        .sentMessages()
        .filter((m) => m.type === 'auth'),
    ).toHaveLength(2);
    act(() => {
      last().serverClose(4401, 'TOKEN_EXPIRED');
    });
    expect(refreshToken).toHaveBeenCalledTimes(2);
    expect(reload).not.toHaveBeenCalled();
    await act(() => new Promise((r) => setTimeout(r, 1_100)));
    act(() => {
      last().accept();
      last().serverClose(4403, 'MANDATE_ENDED');
    });
    expect(reload).toHaveBeenCalledTimes(1);
  });
});
