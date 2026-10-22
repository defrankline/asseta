import type { NotificationDto } from '../api/types';

/**
 * Typed realtime protocol of `/api/v1/ws` (DEC-022, ADR-005; `docs/api.md`). Everything that
 * depends on the wire format lives in `codec.ts` and `authStrategies.ts`.
 */

/** Console context of the connection (managed-service mandate aware); same shape on the wire. */
export type RealtimeScope = { kind: 'platform' } | { kind: 'tenant'; tenantId: string };

/** "Something changed on the server": open screens showing that entity reload themselves. */
export interface EntityChange {
  /** Entity kind, e.g. `alert`, `approval`, `platform_invoice` (see `ENTITY`). */
  entity: string;
  /** Record id when the change concerns one record. */
  id: string | null;
  /** e.g. `created`, `verified`, `voided`; informative only. */
  action: string | null;
}

/** Typed payload of every server event a screen can subscribe to. */
export interface RealtimeEventMap {
  /** A new notification for the signed-in user in the current console. */
  notification: NotificationDto;
  /** The server's unread count (also sent with every `auth_ok`, i.e. after a console switch). */
  unread_count: { count: number };
  'entity.changed': EntityChange;
}

export type RealtimeEventType = keyof RealtimeEventMap;

export type RealtimeEvent = {
  [K in RealtimeEventType]: { type: K; payload: RealtimeEventMap[K] };
}[RealtimeEventType];

/** Messages the client sends. */
export type OutboundMessage =
  | { type: 'auth'; token: string; tenant_id: string | null }
  | { type: 'subscribe'; scope: RealtimeScope }
  | { type: 'ping' }
  | { type: 'pong' };

/** Decoded messages the client receives. */
export type InboundMessage =
  | { kind: 'auth_ok'; unreadCount: number | null; heartbeatSeconds: number | null }
  | { kind: 'auth_error'; code: string; message: string }
  | { kind: 'ping' }
  | { kind: 'pong' }
  /** The token expires in about a minute: send a fresh `auth` on the open socket. */
  | { kind: 'reauth_required' }
  | { kind: 'event'; event: RealtimeEvent };

/** Wire encoding of `{type, payload}` envelopes. */
export interface RealtimeCodec {
  /** Returns null for malformed or unknown messages (they are dropped). */
  decode: (raw: string) => InboundMessage | null;
  encode: (message: OutboundMessage) => string;
}

/**
 * How the access token reaches the server. Never in the URL (it would end up in proxy and server
 * access logs). Both variants re-authenticate on the open socket with an `auth` message.
 */
export interface RealtimeAuthStrategy {
  /** `Sec-WebSocket-Protocol` values for the handshake (undefined: none). */
  protocols: (token: string) => string[] | undefined;
  /** First message after the socket opens (selects the console); the server answers `auth_ok`. */
  firstMessage: (token: string, scope: RealtimeScope) => OutboundMessage;
}

/** Subset of the browser WebSocket used by the client (lets tests inject a fake). */
export interface WebSocketLike {
  readonly readyState: number;
  onopen: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  onerror: ((ev: Event) => void) | null;
  send: (data: string) => void;
  close: (code?: number, reason?: string) => void;
}

export type SocketFactory = (url: string, protocols?: string[]) => WebSocketLike;

export const SOCKET_OPEN = 1;

/** Server close codes (`docs/api.md`). */
export const CLOSE_CODES = {
  /** Not authenticated / token expired / subject changed: refresh the token, then reconnect. */
  auth: 4401,
  /** No access to this console (mandate ended, membership revoked, tenant blocked): stop. */
  access: 4403,
  /** Idle for too long: reconnect. */
  idle: 4408,
} as const;

/**
 * Connection state; the header indicator shows connected / reconnecting / offline / denied
 * (`denied`: the server refused this console, nothing is retried until it changes).
 */
export type ConnectionStatus =
  'idle' | 'connecting' | 'connected' | 'reconnecting' | 'offline' | 'denied';

export function scopeTenantId(scope: RealtimeScope): string | null {
  return scope.kind === 'tenant' ? scope.tenantId : null;
}
