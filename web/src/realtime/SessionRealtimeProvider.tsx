import { useMemo, type ReactNode } from 'react';
import { useAuth } from '../auth/useAuth';
import { appConfig } from '../config/env';
import { useSession } from '../session/useSession';
import type { RealtimeScope } from './protocol';
import { RealtimeProvider } from './RealtimeProvider';

/**
 * The app's realtime connection: runs while signed in with a ready session, subscribes to the
 * current console (platform, or the tenant — including a mandated client) and re-authenticates
 * after every token refresh (e.g. the forced refresh when entering a mandated client).
 */
export function SessionRealtimeProvider({ children }: { children: ReactNode }) {
  const { status: authStatus, getAccessToken, refreshToken, subscribeTokenRefresh } = useAuth();
  const { status, mode, reload } = useSession();
  const tenantId = mode.kind === 'tenant' ? mode.tenantId : null;
  const scope = useMemo<RealtimeScope | null>(() => {
    if (mode.kind === 'platform') return { kind: 'platform' };
    return tenantId === null ? null : { kind: 'tenant', tenantId };
  }, [mode.kind, tenantId]);
  return (
    <RealtimeProvider
      enabled={authStatus === 'authenticated' && status === 'ready' && scope !== null}
      url={appConfig.realtimeUrl}
      getAccessToken={getAccessToken}
      subscribeTokenRefresh={subscribeTokenRefresh}
      scope={scope}
      onAuthRejected={() => {
        // 4401: refresh before the next attempt; a failed refresh starts interactive login.
        refreshToken().catch(() => undefined);
      }}
      onReauthRequired={() => {
        // The refresh listener re-sends the new token on the open socket.
        refreshToken().catch(() => undefined);
      }}
      onAccessDenied={() => {
        // 4403 (mandate ended, membership revoked, tenant blocked): re-read /me; the console
        // switch that follows (if any) reconnects for the new console.
        reload();
      }}
    >
      {children}
    </RealtimeProvider>
  );
}
