import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { RealtimeAuthStrategy, RealtimeCodec, RealtimeScope, SocketFactory } from './protocol';
import { RealtimeClient, type RealtimeClientOptions } from './RealtimeClient';
import { RealtimeContext } from './RealtimeContext';

export interface RealtimeProviderProps {
  children: ReactNode;
  /** Connect only while signed in with a ready session (paused otherwise). */
  enabled: boolean;
  url: string;
  getAccessToken: () => Promise<string | null>;
  /** Registers a token-refresh listener; returns its unsubscribe. */
  subscribeTokenRefresh?: (listener: () => void) => () => void;
  /** Current console; re-subscribed on every change and reconnect. */
  scope: RealtimeScope | null;
  createSocket?: SocketFactory;
  auth?: RealtimeAuthStrategy;
  codec?: RealtimeCodec;
  /** Timing / backoff / randomness overrides (tests). */
  tuning?: Pick<
    RealtimeClientOptions,
    'backoff' | 'heartbeatIntervalMs' | 'heartbeatTimeoutMs' | 'authTimeoutMs' | 'random'
  >;
  /** 4401: refresh the token (the client then reconnects with backoff). */
  onAuthRejected?: (code: string) => void;
  /** 4403: no access to this console any more (e.g. mandate ended): re-evaluate the session. */
  onAccessDenied?: (code: string) => void;
  /** The server warns that the token expires soon: force a refresh. */
  onReauthRequired?: () => void;
}

function scopeKey(scope: RealtimeScope | null): string {
  if (scope === null) return '';
  return scope.kind === 'tenant' ? `tenant:${scope.tenantId}` : 'platform';
}

/**
 * Owns the session's single realtime connection. The client is created once per provider (url,
 * transport and codec are fixed for its lifetime); it runs while `enabled`, goes offline with the
 * browser and wakes up on `online` / the tab becoming visible.
 */
export function RealtimeProvider({
  children,
  enabled,
  url,
  getAccessToken,
  subscribeTokenRefresh,
  scope,
  createSocket,
  auth,
  codec,
  tuning,
  onAuthRejected,
  onAccessDenied,
  onReauthRequired,
}: RealtimeProviderProps) {
  // url, transport and codec are fixed for the provider's lifetime.
  const [client] = useState(
    () =>
      new RealtimeClient({
        url,
        ...(createSocket !== undefined ? { createSocket } : {}),
        ...(auth !== undefined ? { auth } : {}),
        ...(codec !== undefined ? { codec } : {}),
        ...tuning,
      }),
  );
  // Callbacks may change identity every render; the client always uses the latest ones.
  useEffect(() => {
    client.setCallbacks({
      getAccessToken,
      ...(onAuthRejected !== undefined ? { onAuthRejected } : {}),
      ...(onAccessDenied !== undefined ? { onAccessDenied } : {}),
      ...(onReauthRequired !== undefined ? { onReauthRequired } : {}),
    });
  });

  const key = scopeKey(scope);
  const scopeRef = useRef(scope);
  useEffect(() => {
    scopeRef.current = scope;
  });
  useEffect(() => {
    client.setScope(scopeRef.current);
  }, [client, key]);

  useEffect(() => {
    if (!enabled) return undefined;
    client.start();
    if (!navigator.onLine) client.goOffline();
    return () => {
      client.stop();
    };
  }, [client, enabled]);

  useEffect(() => {
    if (subscribeTokenRefresh === undefined) return undefined;
    return subscribeTokenRefresh(() => {
      client.reauthenticate();
    });
  }, [client, subscribeTokenRefresh]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') client.wake();
    };
    const onOnline = () => {
      client.wake();
    };
    const onOffline = () => {
      client.goOffline();
    };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);
    return () => {
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
    };
  }, [client]);

  return <RealtimeContext.Provider value={client}>{children}</RealtimeContext.Provider>;
}
