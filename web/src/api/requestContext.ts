/**
 * Bridge between React providers (auth, session) and the framework-agnostic Axios layer.
 * Providers register handlers at runtime; the HTTP client only reads through this interface.
 */
export interface RequestContext {
  /** Returns a fresh access token (refreshing if needed) or null when unauthenticated. */
  getAccessToken: () => Promise<string | null>;
  /** Returns the currently selected tenant id, or null in platform mode / before selection. */
  getActiveTenantId: () => string | null;
  /** Invoked when the API answers 401; expected to trigger re-login. */
  onUnauthorized: () => void;
  /** Forces a token refresh (ignoring remaining validity) so new Keycloak groups are present. */
  refreshAccessToken: () => Promise<void>;
  /**
   * Invoked when a tenant-scoped call is refused because the managed-service mandate for that
   * tenant is missing or no longer in force (MANDATE_REQUIRED / MANDATE_ENDED).
   */
  onMandateLost: (tenantId: string | null, code: string) => void;
}

const handlers: RequestContext = {
  getAccessToken: () => Promise.resolve(null),
  getActiveTenantId: () => null,
  onUnauthorized: () => undefined,
  refreshAccessToken: () => Promise.resolve(),
  onMandateLost: () => undefined,
};

export const requestContext: RequestContext = {
  getAccessToken: () => handlers.getAccessToken(),
  getActiveTenantId: () => handlers.getActiveTenantId(),
  onUnauthorized: () => {
    handlers.onUnauthorized();
  },
  refreshAccessToken: () => handlers.refreshAccessToken(),
  onMandateLost: (tenantId, code) => {
    handlers.onMandateLost(tenantId, code);
  },
};

/**
 * Register one or more handlers; returns a function restoring the previous ones. Restoring is per
 * handler and only while ours is still installed, so several providers (auth, session) can
 * register and unregister independently without undoing each other.
 */
export function registerRequestContext(partial: Partial<RequestContext>): () => void {
  const keys = Object.keys(partial) as (keyof RequestContext)[];
  const previous: Partial<RequestContext> = {};
  for (const key of keys) assign(previous, key, handlers[key]);
  Object.assign(handlers, partial);
  return () => {
    for (const key of keys) {
      const prev = previous[key];
      if (handlers[key] === partial[key] && prev !== undefined) assign(handlers, key, prev);
    }
  };
}

function assign<K extends keyof RequestContext>(
  target: Partial<RequestContext>,
  key: K,
  value: RequestContext[K],
): void {
  target[key] = value;
}
