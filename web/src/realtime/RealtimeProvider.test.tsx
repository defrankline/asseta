import { act, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { deriveRealtimeUrl } from '../config/env';
import { makeNotification } from '../test/fakeNotificationService';
import { fakeSocketServer, type FakeSocketServer } from '../test/fakeWebSocket';
import { ConnectionIndicator } from './ConnectionIndicator';
import { ENTITY, entityKey, matchesEntityKeys } from './entities';
import { useLiveRefresh, useRealtimeEvent } from './hooks';
import type { RealtimeScope } from './protocol';
import { RealtimeProvider, type RealtimeProviderProps } from './RealtimeProvider';

let server: FakeSocketServer;
const tick = () => act(() => vi.advanceTimersByTimeAsync(0));
const TUNING = { random: () => 0, heartbeatIntervalMs: 60_000, heartbeatTimeoutMs: 5_000 };

beforeEach(() => {
  vi.useFakeTimers();
  server = fakeSocketServer();
});
afterEach(() => {
  vi.useRealTimers();
});

type HarnessProps = Partial<RealtimeProviderProps> & { children?: React.ReactNode };

function Harness({ children, ...props }: HarnessProps) {
  return (
    <RealtimeProvider
      enabled
      url="ws://test/realtime"
      getAccessToken={() => Promise.resolve('tok')}
      scope={{ kind: 'platform' }}
      createSocket={server.factory}
      tuning={TUNING}
      {...props}
    >
      <ConnectionIndicator />
      {children}
    </RealtimeProvider>
  );
}

async function connect() {
  await tick();
  act(() => {
    server.last().accept();
  });
}

describe('RealtimeProvider', () => {
  it('connects while enabled, shows the state in the indicator and pauses when signed out', async () => {
    const view = render(<Harness />);
    await tick();
    expect(screen.getByRole('status', { name: 'Connecting live updates…' })).toBeInTheDocument();
    act(() => {
      server.last().accept();
    });
    expect(screen.getByRole('status', { name: 'Live updates on' })).toBeInTheDocument();
    act(() => {
      server.last().serverClose();
    });
    expect(screen.getByRole('status', { name: 'Reconnecting live updates…' })).toBeInTheDocument();
    view.rerender(<Harness enabled={false} />);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(60_000));
    expect(server.sockets).toHaveLength(1);
  });

  it('goes offline with the browser and resumes on online / tab visibility', async () => {
    render(<Harness />);
    await connect();
    act(() => {
      window.dispatchEvent(new Event('offline'));
    });
    expect(
      screen.getByRole('status', { name: 'Offline: live updates paused' }),
    ).toBeInTheDocument();
    act(() => {
      window.dispatchEvent(new Event('online'));
    });
    await tick();
    expect(server.sockets).toHaveLength(2);
    act(() => {
      server.last().accept();
      server.last().serverClose();
    });
    // Reconnect is scheduled (500 ms); becoming visible reconnects at once.
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await tick();
    expect(server.sockets).toHaveLength(3);
  });

  it('re-authenticates after a token refresh and re-subscribes on console switch', async () => {
    let notifyRefresh: () => void = () => undefined;
    const subscribeTokenRefresh = (l: () => void) => {
      notifyRefresh = l;
      return () => undefined;
    };
    let token = 'tok-1';
    const getAccessToken = () => Promise.resolve(token);
    function Switcher() {
      const [scope, setScope] = useState<RealtimeScope>({ kind: 'platform' });
      return (
        <Harness
          scope={scope}
          getAccessToken={getAccessToken}
          subscribeTokenRefresh={subscribeTokenRefresh}
        >
          <button
            type="button"
            onClick={() => {
              setScope({ kind: 'tenant', tenantId: 't9' });
            }}
          >
            switch
          </button>
        </Harness>
      );
    }
    render(<Switcher />);
    await connect();
    token = 'tok-2';
    act(() => {
      notifyRefresh();
    });
    await tick();
    act(() => {
      screen.getByRole('button', { name: 'switch' }).click();
    });
    expect(server.last().sentMessages()).toEqual([
      { type: 'auth', token: 'tok-1', tenant_id: null },
      { type: 'auth', token: 'tok-2', tenant_id: null },
      { type: 'subscribe', scope: { kind: 'tenant', tenantId: 't9' } },
    ]);
  });
});

describe('RealtimeProvider access loss', () => {
  it('shows the denied state and reports 4403 so the session is re-evaluated', async () => {
    const onAccessDenied = vi.fn();
    render(<Harness onAccessDenied={onAccessDenied} />);
    await connect();
    act(() => {
      server.last().serverClose(4403, 'MANDATE_ENDED');
    });
    expect(
      screen.getByRole('status', { name: 'Live updates unavailable in this console' }),
    ).toBeInTheDocument();
    expect(onAccessDenied).toHaveBeenCalledWith('MANDATE_ENDED');
  });
});

describe('useRealtimeEvent and useLiveRefresh', () => {
  it('delivers typed events to the subscribed component', async () => {
    function Last() {
      const [title, setTitle] = useState('none');
      useRealtimeEvent('notification', (n) => {
        setTitle(n.title);
      });
      return <p>last: {title}</p>;
    }
    render(
      <Harness>
        <Last />
      </Harness>,
    );
    await connect();
    act(() => {
      server.last().receive({
        type: 'notification',
        payload: makeNotification({ title: 'Expense awaiting approval', severity: 'WARNING' }),
      });
    });
    expect(screen.getByText('last: Expense awaiting approval')).toBeInTheDocument();
  });

  it('reloads once per burst of matching changes, and after a reconnect', async () => {
    const reload = vi.fn();
    function Screen() {
      useLiveRefresh([ENTITY.alert, entityKey(ENTITY.platformInvoice, 'inv-1')], reload);
      return null;
    }
    render(
      <Harness>
        <Screen />
      </Harness>,
    );
    await connect();
    const socket = server.last();
    act(() => {
      socket.receive({ type: 'entity.changed', payload: { entity: 'alert', id: 'a1' } });
      socket.receive({ type: 'entity.changed', payload: { entity: 'alert', id: 'a2' } });
      socket.receive({ type: 'entity.changed', payload: { entity: 'approval', id: 'x' } });
      socket.receive({
        type: 'entity.changed',
        payload: { entity: 'platform_invoice', id: 'inv-2' },
      });
    });
    await act(() => vi.advanceTimersByTimeAsync(400));
    expect(reload).toHaveBeenCalledTimes(1);
    act(() => {
      socket.receive({
        type: 'entity.changed',
        payload: { entity: 'platform_invoice', id: 'inv-1' },
      });
    });
    await act(() => vi.advanceTimersByTimeAsync(400));
    expect(reload).toHaveBeenCalledTimes(2);
    act(() => {
      socket.serverClose();
    });
    await act(() => vi.advanceTimersByTimeAsync(500));
    act(() => {
      server.last().accept();
    });
    await act(() => vi.advanceTimersByTimeAsync(400));
    expect(reload).toHaveBeenCalledTimes(3);
  });

  it('is a no-op outside a provider', () => {
    const reload = vi.fn();
    function Screen() {
      useLiveRefresh([ENTITY.alert], reload);
      useRealtimeEvent('notification', reload);
      return <ConnectionIndicator />;
    }
    render(<Screen />);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});

describe('entity keys and realtime URL', () => {
  it('matches kinds and single records', () => {
    const change = { entity: 'alert', id: 'a1', action: null };
    expect(matchesEntityKeys(change, ['alert'])).toBe(true);
    expect(matchesEntityKeys(change, ['alert:a1'])).toBe(true);
    expect(matchesEntityKeys(change, ['alert:a2', 'approval'])).toBe(false);
  });

  it('derives ws/wss URLs from the API base without credentials', () => {
    const https = { protocol: 'https:', host: 'app.asseta.test' };
    expect(deriveRealtimeUrl('/api/v1', https)).toBe('wss://app.asseta.test/api/v1/ws');
    expect(deriveRealtimeUrl('/api/v1/', { protocol: 'http:', host: 'localhost:5173' })).toBe(
      'ws://localhost:5173/api/v1/ws',
    );
    expect(deriveRealtimeUrl('https://api.asseta.test/api/v1', https)).toBe(
      'wss://api.asseta.test/api/v1/ws',
    );
    expect(deriveRealtimeUrl('/api/v1', https, ' wss://rt.asseta.test/ws ')).toBe(
      'wss://rt.asseta.test/ws',
    );
  });
});
