import { notificationSchema } from '../api/services/notificationSchemas';
import type { EntityChange, InboundMessage, OutboundMessage, RealtimeCodec } from './protocol';

/** JSON `{"type", "payload"}` envelopes of `/api/v1/ws` (`docs/api.md`). */

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function str(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function count(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : null;
}

function parseEntityChange(data: Record<string, unknown>): EntityChange | null {
  const entity = str(data.entity);
  if (entity === null || entity === '') return null;
  return { entity, id: str(data.id), action: str(data.action) };
}

function decodeEvent(type: string, payload: Record<string, unknown>): InboundMessage | null {
  switch (type) {
    case 'notification': {
      if (!notificationSchema.isValidSync(payload)) return null;
      return {
        kind: 'event',
        event: { type: 'notification', payload: notificationSchema.validateSync(payload) },
      };
    }
    case 'unread_count': {
      const c = count(payload.count);
      return c === null
        ? null
        : { kind: 'event', event: { type: 'unread_count', payload: { count: c } } };
    }
    case 'entity.changed': {
      const change = parseEntityChange(payload);
      return change === null
        ? null
        : { kind: 'event', event: { type: 'entity.changed', payload: change } };
    }
    default:
      return null;
  }
}

export const jsonCodec: RealtimeCodec = {
  decode(raw) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return null;
    }
    if (!isRecord(parsed)) return null;
    const type = str(parsed.type);
    const payload = isRecord(parsed.payload) ? parsed.payload : {};
    switch (type) {
      case null:
        return null;
      case 'auth_ok': {
        const hb = payload.heartbeat_seconds;
        return {
          kind: 'auth_ok',
          unreadCount: count(payload.unread_count),
          heartbeatSeconds: typeof hb === 'number' && hb > 0 ? hb : null,
        };
      }
      case 'auth_error':
        return {
          kind: 'auth_error',
          code: str(payload.code) ?? 'NOT_AUTHENTICATED',
          message: str(payload.message) ?? 'Realtime authentication failed.',
        };
      case 'ping':
        return { kind: 'ping' };
      case 'pong':
        return { kind: 'pong' };
      case 'reauth_required':
        return { kind: 'reauth_required' };
      default:
        return decodeEvent(type, payload);
    }
  },
  encode(message: OutboundMessage) {
    return JSON.stringify(message);
  },
};
