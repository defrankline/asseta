import { firstMessageAuth } from './authStrategies';
import { backoffDelay, type BackoffOptions } from './backoff';
import { jsonCodec } from './codec';
import {
  CLOSE_CODES,
  SOCKET_OPEN,
  scopeTenantId,
  type ConnectionStatus,
  type InboundMessage,
  type OutboundMessage,
  type RealtimeAuthStrategy,
  type RealtimeCodec,
  type RealtimeEventMap,
  type RealtimeEventType,
  type RealtimeScope,
  type SocketFactory,
  type WebSocketLike,
} from './protocol';

/** Callbacks into the app (React passes its latest ones with `setCallbacks`). */
export interface RealtimeCallbacks {
  /** Fresh access token (refreshed if close to expiry); null when signed out. */
  getAccessToken: () => Promise<string | null>;
  /** 4401: the token was refused or expired; refresh it before the next attempt. */
  onAuthRejected?: (code: string) => void;
  /** 4403: no access to this console (e.g. mandate ended); re-evaluate the session. */
  onAccessDenied?: (code: string) => void;
  /** `reauth_required`: force a token refresh (its listener then calls `reauthenticate`). */
  onReauthRequired?: () => void;
}

export interface RealtimeClientOptions extends Partial<RealtimeCallbacks> {
  url: string;
  createSocket?: SocketFactory;
  auth?: RealtimeAuthStrategy;
  codec?: RealtimeCodec;
  backoff?: BackoffOptions;
  /** Client ping interval while connected (default 25 s; the server closes after 75 s idle). */
  heartbeatIntervalMs?: number;
  /** No message at all within this time after a ping ⇒ the link is dead (default 10 s). */
  heartbeatTimeoutMs?: number;
  /** Time allowed for `auth_ok` after opening (default 10 s, as the server's). */
  authTimeoutMs?: number;
  random?: () => number;
}

type Handler<K extends RealtimeEventType> = (payload: RealtimeEventMap[K]) => void;
type AnyHandler = (payload: never) => void;
type Timer = ReturnType<typeof setTimeout>;

const defaultSocketFactory: SocketFactory = (url, protocols) => new WebSocket(url, protocols);

/** Close codes the client itself uses when it abandons a socket. */
export const CLOSE_HEARTBEAT = 4000;
export const CLOSE_AUTH_TIMEOUT = 4001;
const CLOSE_NORMAL = 1000;

/**
 * One shared, authenticated WebSocket per signed-in session: heartbeat, exponential backoff
 * reconnect with jitter, re-auth on the open socket, console subscription, server close codes
 * (4401 refresh + reconnect, 4403 stop, 4408 reconnect) and typed dispatch. Framework-agnostic;
 * `RealtimeProvider` drives it from React.
 */
export class RealtimeClient {
  private readonly opts: Required<
    Omit<RealtimeClientOptions, keyof RealtimeCallbacks | 'backoff'>
  > &
    Pick<RealtimeClientOptions, 'backoff'>;
  private callbacks: RealtimeCallbacks;
  private socket: WebSocketLike | null = null;
  private status: ConnectionStatus = 'idle';
  private running = false;
  private offline = false;
  private denied = false;
  private everConnected = false;
  private attempt = 0;
  /** Bumped whenever the current socket is abandoned; stale callbacks compare against it. */
  private generation = 0;
  private scope: RealtimeScope | null = null;
  private lastErrorCode: string | null = null;
  private reconnectTimer: Timer | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private pongTimer: Timer | null = null;
  private authTimer: Timer | null = null;
  private readonly handlers = new Map<RealtimeEventType, Set<AnyHandler>>();
  private readonly statusListeners = new Set<(status: ConnectionStatus) => void>();
  private readonly resyncListeners = new Set<() => void>();

  constructor({
    getAccessToken,
    onAuthRejected,
    onAccessDenied,
    onReauthRequired,
    ...options
  }: RealtimeClientOptions) {
    this.callbacks = {
      getAccessToken: getAccessToken ?? (() => Promise.resolve(null)),
      ...(onAuthRejected !== undefined ? { onAuthRejected } : {}),
      ...(onAccessDenied !== undefined ? { onAccessDenied } : {}),
      ...(onReauthRequired !== undefined ? { onReauthRequired } : {}),
    };
    this.opts = {
      createSocket: defaultSocketFactory,
      auth: firstMessageAuth,
      codec: jsonCodec,
      heartbeatIntervalMs: 25_000,
      heartbeatTimeoutMs: 10_000,
      authTimeoutMs: 10_000,
      random: Math.random,
      ...options,
    };
  }

  /** Arrow function: usable directly as a `useSyncExternalStore` snapshot getter. */
  readonly getStatus = (): ConnectionStatus => this.status;

  setCallbacks(callbacks: RealtimeCallbacks): void {
    this.callbacks = callbacks;
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.attempt = 0;
    void this.connect();
  }

  /** Signed out / unmounted: close and stop reconnecting. */
  stop(): void {
    this.running = false;
    this.offline = false;
    this.denied = false;
    this.everConnected = false;
    this.abandonSocket(CLOSE_NORMAL, 'stopped');
    this.clearReconnect();
    this.setStatus('idle');
  }

  /** Console switched: re-authorize the open connection for it (or connect / retry). */
  setScope(scope: RealtimeScope | null): void {
    const same = sameScope(this.scope, scope);
    this.scope = scope;
    if (same || !this.running) return;
    if (scope !== null && this.status === 'connected') {
      this.send({ type: 'subscribe', scope });
      return;
    }
    this.denied = false;
    if (!this.offline) this.reconnectNow();
  }

  /** The access token was refreshed: send it on the open socket (same user, same console). */
  reauthenticate(): void {
    if (!this.running || this.offline || this.denied) return;
    if (this.status !== 'connected') {
      this.reconnectNow();
      return;
    }
    const gen = this.generation;
    void this.callbacks.getAccessToken().then((token) => {
      if (gen !== this.generation || token === null || this.scope === null) return;
      this.send({ type: 'auth', token, tenant_id: scopeTenantId(this.scope) });
    });
  }

  /** Tab visible again / browser back online: verify a live link or reconnect immediately. */
  wake(): void {
    if (!this.running) return;
    const resume = this.offline || this.denied;
    this.offline = false;
    this.denied = false;
    if (!resume && this.status === 'connected') {
      this.ping();
      return;
    }
    if (!resume && this.status === 'connecting' && this.socket !== null) return;
    this.reconnectNow();
  }

  /** Browser reports no network: stop retrying until `wake()`. */
  goOffline(): void {
    if (!this.running) return;
    this.offline = true;
    this.abandonSocket(CLOSE_NORMAL, 'offline');
    this.clearReconnect();
    this.setStatus('offline');
  }

  subscribe<K extends RealtimeEventType>(type: K, handler: Handler<K>): () => void {
    let set = this.handlers.get(type);
    if (set === undefined) {
      set = new Set();
      this.handlers.set(type, set);
    }
    const entry = handler as AnyHandler;
    set.add(entry);
    return () => {
      set.delete(entry);
    };
  }

  readonly onStatus = (listener: (status: ConnectionStatus) => void): (() => void) => {
    this.statusListeners.add(listener);
    return () => {
      this.statusListeners.delete(listener);
    };
  };

  /** Called when a connection comes back after a drop: events may have been missed. */
  onResync(listener: () => void): () => void {
    this.resyncListeners.add(listener);
    return () => {
      this.resyncListeners.delete(listener);
    };
  }

  // ---- internals ----

  private async connect(): Promise<void> {
    if (!this.running || this.offline || this.denied || this.scope === null) return;
    const gen = ++this.generation;
    this.setStatus(this.everConnected || this.attempt > 0 ? 'reconnecting' : 'connecting');
    let token: string | null;
    try {
      token = await this.callbacks.getAccessToken();
    } catch {
      token = null;
    }
    const scope = this.currentScope(); // may have changed while awaiting the token
    if (this.superseded(gen) || scope === null) return;
    if (token === null) {
      this.scheduleReconnect();
      return;
    }
    let socket: WebSocketLike;
    try {
      socket = this.opts.createSocket(this.opts.url, this.opts.auth.protocols(token));
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.socket = socket;
    this.lastErrorCode = null;
    socket.onopen = () => {
      if (gen !== this.generation) return;
      this.send(this.opts.auth.firstMessage(token, this.scope ?? scope));
      this.authTimer = setTimeout(() => {
        this.dropAndRetry(CLOSE_AUTH_TIMEOUT, 'auth timeout');
      }, this.opts.authTimeoutMs);
    };
    socket.onmessage = (ev: MessageEvent) => {
      if (gen !== this.generation || typeof ev.data !== 'string') return;
      this.clearPong();
      const message = this.opts.codec.decode(ev.data);
      if (message !== null) this.handle(message);
    };
    socket.onclose = (ev: CloseEvent) => {
      if (gen !== this.generation) return;
      this.socket = null;
      this.clearSocketTimers();
      this.onServerClose(ev.code, ev.reason !== '' ? ev.reason : this.lastErrorCode);
    };
    socket.onerror = () => undefined; // onclose follows and drives the retry
  }

  private onServerClose(code: number, reason: string | null): void {
    switch (code) {
      case CLOSE_CODES.auth:
        this.callbacks.onAuthRejected?.(reason ?? 'NOT_AUTHENTICATED');
        this.scheduleReconnect();
        return;
      case CLOSE_CODES.access:
        this.denied = true;
        this.clearReconnect();
        this.setStatus('denied');
        this.callbacks.onAccessDenied?.(reason ?? 'PERMISSION_DENIED');
        return;
      case CLOSE_CODES.idle:
        this.attempt = 0;
        this.scheduleReconnect();
        return;
      default:
        this.scheduleReconnect();
    }
  }

  private currentScope(): RealtimeScope | null {
    return this.scope;
  }

  /** The attempt `gen` was abandoned (stop, offline, denied or a newer attempt) while awaiting. */
  private superseded(gen: number): boolean {
    return gen !== this.generation || !this.running || this.offline || this.denied;
  }

  private handle(message: InboundMessage): void {
    switch (message.kind) {
      case 'auth_ok':
        if (this.status !== 'connected') this.onAuthenticated();
        if (message.unreadCount !== null) {
          this.dispatch('unread_count', { count: message.unreadCount });
        }
        return;
      case 'auth_error':
        // The server closes next (4401 / 4403); the close code decides what happens.
        this.lastErrorCode = message.code;
        return;
      case 'ping':
        this.send({ type: 'pong' });
        return;
      case 'pong':
        return;
      case 'reauth_required':
        if (this.callbacks.onReauthRequired !== undefined) this.callbacks.onReauthRequired();
        else this.reauthenticate();
        return;
      case 'event':
        this.dispatch(message.event.type, message.event.payload);
    }
  }

  private dispatch(type: RealtimeEventType, payload: unknown): void {
    const set = this.handlers.get(type);
    if (set === undefined) return;
    for (const handler of [...set]) {
      try {
        (handler as (p: unknown) => void)(payload);
      } catch (err) {
        console.error('Realtime handler failed', err);
      }
    }
  }

  private onAuthenticated(): void {
    if (this.authTimer !== null) clearTimeout(this.authTimer);
    this.authTimer = null;
    const resync = this.everConnected;
    this.everConnected = true;
    this.attempt = 0;
    this.setStatus('connected');
    this.startHeartbeat();
    if (resync) for (const l of [...this.resyncListeners]) l();
  }

  private startHeartbeat(): void {
    if (this.heartbeatTimer !== null) clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = setInterval(() => {
      this.ping();
    }, this.opts.heartbeatIntervalMs);
  }

  private ping(): void {
    if (this.pongTimer !== null) return;
    this.send({ type: 'ping' });
    this.pongTimer = setTimeout(() => {
      this.pongTimer = null;
      this.dropAndRetry(CLOSE_HEARTBEAT, 'heartbeat timeout');
    }, this.opts.heartbeatTimeoutMs);
  }

  private send(message: OutboundMessage): void {
    const socket = this.socket;
    if (socket === null || socket.readyState !== SOCKET_OPEN) return;
    try {
      socket.send(this.opts.codec.encode(message));
    } catch {
      // A failing send is followed by close; the reconnect loop takes over.
    }
  }

  private dropAndRetry(code: number, reason: string): void {
    this.abandonSocket(code, reason);
    this.scheduleReconnect();
  }

  private reconnectNow(): void {
    this.abandonSocket(CLOSE_NORMAL, 'reconnect');
    this.clearReconnect();
    this.attempt = 0;
    void this.connect();
  }

  /** Detach and close the current socket without triggering its onclose handling. */
  private abandonSocket(code: number, reason: string): void {
    this.generation++;
    this.clearSocketTimers();
    const socket = this.socket;
    this.socket = null;
    if (socket === null) return;
    socket.onopen = null;
    socket.onmessage = null;
    socket.onclose = null;
    socket.onerror = null;
    try {
      socket.close(code, reason);
    } catch {
      // Already closed.
    }
  }

  private scheduleReconnect(): void {
    if (!this.running || this.offline || this.denied) return;
    this.clearReconnect();
    const delay = backoffDelay(this.attempt, this.opts.backoff, this.opts.random);
    this.attempt++;
    this.setStatus('reconnecting');
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      void this.connect();
    }, delay);
  }

  private clearReconnect(): void {
    if (this.reconnectTimer !== null) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
  }

  private clearPong(): void {
    if (this.pongTimer !== null) clearTimeout(this.pongTimer);
    this.pongTimer = null;
  }

  private clearSocketTimers(): void {
    this.clearPong();
    if (this.heartbeatTimer !== null) clearInterval(this.heartbeatTimer);
    if (this.authTimer !== null) clearTimeout(this.authTimer);
    this.heartbeatTimer = null;
    this.authTimer = null;
  }

  private setStatus(status: ConnectionStatus): void {
    if (this.status === status) return;
    this.status = status;
    for (const l of [...this.statusListeners]) l(status);
  }
}

function sameScope(a: RealtimeScope | null, b: RealtimeScope | null): boolean {
  if (a === null || b === null) return a === b;
  return a.kind === b.kind && scopeTenantId(a) === scopeTenantId(b);
}
