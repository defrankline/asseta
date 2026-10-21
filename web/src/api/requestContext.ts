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
}

const handlers: RequestContext = {
  getAccessToken: () => Promise.resolve(null),
  getActiveTenantId: () => null,
  onUnauthorized: () => undefined,
};

export const requestContext: RequestContext = {
  getAccessToken: () => handlers.getAccessToken(),
  getActiveTenantId: () => handlers.getActiveTenantId(),
  onUnauthorized: () => {
    handlers.onUnauthorized();
  },
};

/** Register one or more handlers; returns a function restoring the previous ones. */
export function registerRequestContext(partial: Partial<RequestContext>): () => void {
  const previous = { ...handlers };
  Object.assign(handlers, partial);
  return () => {
    Object.assign(handlers, previous);
  };
}
