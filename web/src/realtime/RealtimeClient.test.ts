import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { makeNotification } from '../test/fakeNotificationService';
import { fakeSocketServer, type FakeSocketServer } from '../test/fakeWebSocket';
import { subprotocolAuth } from './authStrategies';
import { backoffDelay } from './backoff';
import { jsonCodec } from './codec';
import {
  CLOSE_AUTH_TIMEOUT,
  CLOSE_HEARTBEAT,
  RealtimeClient,
  type RealtimeClientOptions,
} from './RealtimeClient';

const URL = 'wss://app.example/api/v1/ws';
const TENANT = { kind: 'tenant', tenantId: 't1' } as const;

let server: FakeSocketServer;
let token: string;

function makeClient(overrides: Partial<RealtimeClientOptions> = {}) {
  const client = new RealtimeClient({
    url: URL,
    getAccessToken: () => Promise.resolve(token),
    createSocket: server.factory,
    random: () => 0, // jitter share 0.5 ⇒ delay = half of the exponential step
    heartbeatIntervalMs: 1_000,
    heartbeatTimeoutMs: 500,
    authTimeoutMs: 2_000,
    ...overrides,
  });
  client.setScope(TENANT);
  return client;
}

/** Flush the token promise (connect is async). */
const tick = () => vi.advanceTimersByTimeAsync(0);

async function connected(overrides: Partial<RealtimeClientOptions> = {}) {
  const client = makeClient(overrides);
  client.start();
  await tick();
  server.last().accept();
  return client;
}

beforeEach(() => {
  vi.useFakeTimers();
  server = fakeSocketServer();
  token = 'tok-1';
});
afterEach(() => {
  vi.useRealTimers();
});

describe('backoffDelay', () => {
  it('grows exponentially, is capped, and spreads with jitter', () => {
    const opts = { baseMs: 1_000, maxMs: 8_000, jitter: 0.5 };
    expect([0, 1, 2, 3, 4].map((a) => backoffDelay(a, opts, () => 0))).toEqual([
      500, 1_000, 2_000, 4_000, 4_000,
    ]);
    expect([0, 1, 2, 3, 4].map((a) => backoffDelay(a, opts, () => 1))).toEqual([
      1_000, 2_000, 4_000, 8_000, 8_000,
    ]);
    expect(backoffDelay(2, { ...opts, jitter: 0 }, () => 0.7)).toBe(4_000);
  });
});

describe('codec ({type, payload} envelopes)', () => {
  it('decodes server messages and drops malformed ones', () => {
    const n = makeNotification({ title: 'Geofence exit' });
    expect(jsonCodec.decode(JSON.stringify({ type: 'notification', payload: n }))).toEqual({
      kind: 'event',
      event: { type: 'notification', payload: n },
    });
    expect(
      jsonCodec.decode('{"type":"auth_ok","payload":{"unread_count":4,"heartbeat_seconds":25}}'),
    ).toEqual({ kind: 'auth_ok', unreadCount: 4, heartbeatSeconds: 25 });
    expect(jsonCodec.decode('{"type":"auth_error","payload":{"code":"MANDATE_ENDED"}}')).toEqual(
      expect.objectContaining({ kind: 'auth_error', code: 'MANDATE_ENDED' }),
    );
    expect(jsonCodec.decode('{"type":"reauth_required","payload":{"expires_at":1}}')).toEqual({
      kind: 'reauth_required',
    });
    expect(jsonCodec.decode('{"type":"unread_count","payload":{"count":-1}}')).toBeNull();
    expect(jsonCodec.decode('{"type":"notification","payload":{"id":"x"}}')).toBeNull();
    expect(jsonCodec.decode('nope')).toBeNull();
    expect(jsonCodec.encode({ type: 'subscribe', scope: TENANT })).toBe(
      '{"type":"subscribe","scope":{"kind":"tenant","tenantId":"t1"}}',
    );
  });
});

describe('RealtimeClient connection and auth', () => {
  it('sends the token and console in the first message (never the URL)', async () => {
    const client = makeClient();
    const statuses: string[] = [];
    const unread = vi.fn();
    client.onStatus((s) => statuses.push(s));
    client.subscribe('unread_count', unread);
    client.start();
    await tick();
    const socket = server.last();
    expect(socket.url).toBe(URL);
    expect(socket.url).not.toContain('tok-1');
    expect(socket.protocols).toBeUndefined();
    socket.open();
    expect(client.getStatus()).toBe('connecting');
    expect(socket.sentMessages()[0]).toEqual({ type: 'auth', token: 'tok-1', tenant_id: 't1' });
    socket.accept(3);
    expect(client.getStatus()).toBe('connected');
    expect(unread).toHaveBeenCalledWith({ count: 3 });
    expect(statuses).toEqual(['connecting', 'connected']);
  });

  it('platform console sends tenant_id null', async () => {
    const client = makeClient();
    client.setScope({ kind: 'platform' });
    client.start();
    await tick();
    server.last().open();
    expect(server.last().sentMessages()[0]).toEqual({
      type: 'auth',
      token: 'tok-1',
      tenant_id: null,
    });
  });

  it('supports Sec-WebSocket-Protocol: asseta.v1, bearer.<jwt> with a subscribe first', async () => {
    const client = makeClient({ auth: subprotocolAuth });
    client.start();
    await tick();
    const socket = server.last();
    expect(socket.url).toBe(URL);
    expect(socket.protocols).toEqual(['asseta.v1', 'bearer.tok-1']);
    socket.open();
    expect(socket.sentMessages()).toEqual([{ type: 'subscribe', scope: TENANT }]);
    socket.accept();
    expect(client.getStatus()).toBe('connected');
  });

  it('waits for a console before connecting', async () => {
    const client = new RealtimeClient({
      url: URL,
      getAccessToken: () => Promise.resolve(token),
      createSocket: server.factory,
    });
    client.start();
    await tick();
    expect(server.sockets).toHaveLength(0);
    client.setScope({ kind: 'platform' });
    await tick();
    expect(server.sockets).toHaveLength(1);
  });

  it('reconnects when auth is not acknowledged in time', async () => {
    const client = makeClient();
    client.start();
    await tick();
    server.last().open();
    await vi.advanceTimersByTimeAsync(2_000);
    expect(server.sockets[0]?.closedWith?.code).toBe(CLOSE_AUTH_TIMEOUT);
    expect(client.getStatus()).toBe('reconnecting');
    await vi.advanceTimersByTimeAsync(500);
    expect(server.sockets).toHaveLength(2);
  });

  it('waits and retries while no token is available', async () => {
    let available: string | null = null;
    const client = makeClient({ getAccessToken: () => Promise.resolve(available) });
    client.start();
    await tick();
    expect(server.sockets).toHaveLength(0);
    expect(client.getStatus()).toBe('reconnecting');
    available = 'late';
    await vi.advanceTimersByTimeAsync(500);
    expect(server.sockets).toHaveLength(1);
  });
});

describe('RealtimeClient close codes', () => {
  it('4401: asks for a token refresh, then reconnects with the fresh token', async () => {
    const onAuthRejected = vi.fn(() => {
      token = 'tok-2';
    });
    await connected({ onAuthRejected });
    server.last().receive({ type: 'auth_error', payload: { code: 'TOKEN_EXPIRED' } });
    server.last().serverClose(4401);
    expect(onAuthRejected).toHaveBeenCalledWith('TOKEN_EXPIRED');
    await vi.advanceTimersByTimeAsync(500);
    server.last().open();
    expect(server.last().sentMessages()[0]).toMatchObject({ type: 'auth', token: 'tok-2' });
  });

  it('4403: stops, reports the code and only retries on wake or a console change', async () => {
    const onAccessDenied = vi.fn();
    const client = await connected({ onAccessDenied });
    server.last().serverClose(4403, 'MANDATE_ENDED');
    expect(client.getStatus()).toBe('denied');
    expect(onAccessDenied).toHaveBeenCalledWith('MANDATE_ENDED');
    await vi.advanceTimersByTimeAsync(120_000);
    expect(server.sockets).toHaveLength(1);
    client.setScope({ kind: 'platform' });
    await tick();
    expect(server.sockets).toHaveLength(2);
    server.last().serverClose(4403, 'PLATFORM_REQUIRED');
    client.wake();
    await tick();
    expect(server.sockets).toHaveLength(3);
  });

  it('4408 (idle): reconnects after the shortest backoff', async () => {
    const client = await connected({ backoff: { baseMs: 1_000 } });
    server.last().serverClose(1006);
    await vi.advanceTimersByTimeAsync(500);
    server.last().accept(); // attempt reset after success
    server.last().serverClose(4408, 'IDLE_TIMEOUT');
    expect(client.getStatus()).toBe('reconnecting');
    await vi.advanceTimersByTimeAsync(500);
    expect(server.sockets).toHaveLength(3);
  });
});

describe('RealtimeClient reconnect, heartbeat and offline', () => {
  it('backs off exponentially with jitter, resets after success and signals a resync', async () => {
    const resync = vi.fn();
    const client = makeClient();
    client.onResync(resync);
    client.start();
    await tick();
    server.last().accept();
    expect(resync).not.toHaveBeenCalled();
    server.last().serverClose();
    await vi.advanceTimersByTimeAsync(499);
    expect(server.sockets).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(server.sockets).toHaveLength(2);
    server.last().serverClose(); // ⇒ 1 000 ms
    await vi.advanceTimersByTimeAsync(999);
    expect(server.sockets).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(server.sockets).toHaveLength(3);
    server.last().serverClose(); // ⇒ 2 000 ms
    await vi.advanceTimersByTimeAsync(2_000);
    server.last().accept();
    expect(client.getStatus()).toBe('connected');
    expect(resync).toHaveBeenCalledTimes(1);
    server.last().serverClose(); // reset: back to 500 ms
    await vi.advanceTimersByTimeAsync(500);
    expect(server.sockets).toHaveLength(5);
  });

  it('answers server pings, pings itself and drops a link that stops answering', async () => {
    await connected();
    const socket = server.last();
    socket.receive({ type: 'ping' });
    expect(socket.sentMessages().at(-1)).toEqual({ type: 'pong' });
    await vi.advanceTimersByTimeAsync(1_000);
    expect(socket.sentMessages().at(-1)).toEqual({ type: 'ping' });
    socket.receive({ type: 'pong' });
    await vi.advanceTimersByTimeAsync(1_000);
    expect(socket.closedWith).toBeNull();
    await vi.advanceTimersByTimeAsync(500); // second ping unanswered
    expect(socket.closedWith?.code).toBe(CLOSE_HEARTBEAT);
    await vi.advanceTimersByTimeAsync(500);
    expect(server.sockets).toHaveLength(2);
  });

  it('goes offline without retrying and wakes up immediately', async () => {
    const client = await connected();
    client.goOffline();
    expect(client.getStatus()).toBe('offline');
    await vi.advanceTimersByTimeAsync(60_000);
    expect(server.sockets).toHaveLength(1);
    client.wake();
    await tick();
    expect(server.sockets).toHaveLength(2);
  });

  it('wake() skips the backoff wait while reconnecting and only pings when connected', async () => {
    const client = await connected({ backoff: { baseMs: 10_000, maxMs: 10_000 } });
    client.wake();
    expect(server.last().sentMessages().at(-1)).toEqual({ type: 'ping' });
    server.last().serverClose();
    client.wake();
    await tick();
    expect(server.sockets).toHaveLength(2);
  });

  it('stop() closes the socket and never reconnects', async () => {
    const client = await connected();
    client.stop();
    expect(client.getStatus()).toBe('idle');
    expect(server.sockets[0]?.closedWith?.code).toBe(1000);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(server.sockets).toHaveLength(1);
  });
});

describe('RealtimeClient re-auth, console switch and dispatch', () => {
  it('re-sends auth with the refreshed token on the open socket', async () => {
    const client = await connected();
    token = 'tok-2';
    client.reauthenticate();
    await tick();
    expect(
      server
        .last()
        .sentMessages()
        .filter((m) => m.type === 'auth'),
    ).toEqual([
      { type: 'auth', token: 'tok-1', tenant_id: 't1' },
      { type: 'auth', token: 'tok-2', tenant_id: 't1' },
    ]);
    expect(server.sockets).toHaveLength(1);
  });

  it('reauth_required forces a refresh (or re-auths directly without a callback)', async () => {
    const onReauthRequired = vi.fn();
    await connected({ onReauthRequired });
    server.last().receive({ type: 'reauth_required', payload: { expires_at: 1 } });
    expect(onReauthRequired).toHaveBeenCalledTimes(1);
    const plain = await connected();
    token = 'tok-3';
    server.last().receive({ type: 'reauth_required', payload: { expires_at: 1 } });
    await tick();
    expect(server.last().sentMessages().at(-1)).toEqual({
      type: 'auth',
      token: 'tok-3',
      tenant_id: 't1',
    });
    plain.stop();
  });

  it('switches console with subscribe on the open socket', async () => {
    const client = await connected();
    client.setScope({ kind: 'tenant', tenantId: 't2' });
    client.setScope({ kind: 'tenant', tenantId: 't2' }); // unchanged: nothing sent
    expect(
      server
        .last()
        .sentMessages()
        .filter((m) => m.type === 'subscribe'),
    ).toEqual([{ type: 'subscribe', scope: { kind: 'tenant', tenantId: 't2' } }]);
    server.last().serverClose();
    await vi.advanceTimersByTimeAsync(500);
    server.last().open();
    expect(server.last().sentMessages()[0]).toMatchObject({ type: 'auth', tenant_id: 't2' });
  });

  it('dispatches typed events to subscribers only, isolating failing handlers', async () => {
    const client = makeClient();
    const onNotification = vi.fn();
    const onChange = vi.fn();
    const failing = vi.fn(() => {
      throw new Error('boom');
    });
    const error = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    client.subscribe('notification', failing);
    const off = client.subscribe('notification', onNotification);
    client.subscribe('entity.changed', onChange);
    client.start();
    await tick();
    const socket = server.last();
    socket.accept();
    const n = makeNotification();
    socket.receive({ type: 'notification', payload: n });
    socket.receive({ type: 'notification', payload: { ...n, severity: 'SUCCESS' } });
    socket.receive({ type: 'entity.changed', payload: { entity: 'alert', id: 'a1' } });
    expect(onNotification).toHaveBeenCalledTimes(1);
    expect(onNotification).toHaveBeenCalledWith(n);
    expect(failing).toHaveBeenCalledTimes(1);
    expect(error).toHaveBeenCalled();
    expect(onChange).toHaveBeenCalledWith({ entity: 'alert', id: 'a1', action: null });
    off();
    socket.receive({ type: 'notification', payload: n });
    expect(onNotification).toHaveBeenCalledTimes(1);
  });
});
