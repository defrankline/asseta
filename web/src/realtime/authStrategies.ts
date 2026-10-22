import { scopeTenantId, type RealtimeAuthStrategy } from './protocol';

/** Sub-protocol the server selects (`docs/api.md`). */
export const REALTIME_SUBPROTOCOL = 'asseta.v1';
const BEARER_PREFIX = 'bearer.';

/**
 * Token in the first message: `{"type":"auth","token":…,"tenant_id":…|null}` (null = platform
 * console). Default.
 */
export const firstMessageAuth: RealtimeAuthStrategy = {
  protocols: () => undefined,
  firstMessage: (token, scope) => ({ type: 'auth', token, tenant_id: scopeTenantId(scope) }),
};

/**
 * Token in the handshake: `Sec-WebSocket-Protocol: asseta.v1, bearer.<jwt>`; the first message
 * then only selects the console (`subscribe`).
 */
export const subprotocolAuth: RealtimeAuthStrategy = {
  protocols: (token) => [REALTIME_SUBPROTOCOL, `${BEARER_PREFIX}${token}`],
  firstMessage: (_token, scope) => ({ type: 'subscribe', scope }),
};
