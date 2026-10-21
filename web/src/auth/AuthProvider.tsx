import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { registerRequestContext } from '../api/requestContext';
import { AuthContext, type AuthContextValue, type AuthStatus } from './AuthContext';
import {
  createKeycloakClient,
  keycloakInitOptions,
  TOKEN_MIN_VALIDITY_SECONDS,
  type AuthClient,
} from './keycloak';

interface AuthProviderProps {
  children: ReactNode;
  /** Injectable for tests; defaults to a keycloak-js instance built from env. */
  client?: AuthClient;
}

const initialised = new WeakMap<AuthClient, Promise<boolean>>();

/** keycloak-js may only be initialised once per instance (StrictMode runs effects twice). */
function initOnce(client: AuthClient): Promise<boolean> {
  const existing = initialised.get(client);
  if (existing) return existing;
  const p = client.init(keycloakInitOptions(window.location.origin));
  initialised.set(client, p);
  return p;
}

/** Silent refresh: renew shortly before expiry; fall back to interactive login on failure. */
function attachRefreshHandlers(kc: AuthClient, onFailure: () => void): void {
  kc.onTokenExpired = () => {
    kc.updateToken(TOKEN_MIN_VALIDITY_SECONDS).catch(onFailure);
  };
  kc.onAuthRefreshError = onFailure;
}

export function AuthProvider({ children, client }: AuthProviderProps) {
  const [kc] = useState<AuthClient>(() => client ?? createKeycloakClient());
  const [status, setStatus] = useState<AuthStatus>('initializing');
  const [error, setError] = useState<string | null>(null);
  const redirecting = useRef(false);

  const login = useCallback(() => {
    if (redirecting.current) return;
    redirecting.current = true;
    void kc.login({ redirectUri: window.location.href });
  }, [kc]);

  const logout = useCallback(() => {
    void kc.logout({ redirectUri: window.location.origin });
  }, [kc]);

  const getAccessToken = useCallback(async (): Promise<string | null> => {
    if (kc.authenticated !== true) return null;
    try {
      await kc.updateToken(TOKEN_MIN_VALIDITY_SECONDS);
      return kc.token ?? null;
    } catch {
      login();
      return null;
    }
  }, [kc, login]);

  useEffect(() => {
    let active = true;
    attachRefreshHandlers(kc, login);
    initOnce(kc)
      .then((authenticated) => {
        if (active) setStatus(authenticated ? 'authenticated' : 'unauthenticated');
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Identity provider unavailable.');
        setStatus('error');
      });
    return () => {
      active = false;
    };
  }, [kc, login]);

  useEffect(
    () => registerRequestContext({ getAccessToken, onUnauthorized: login }),
    [getAccessToken, login],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      subject: status === 'authenticated' ? (kc.tokenParsed?.sub ?? null) : null,
      username:
        status === 'authenticated'
          ? (kc.tokenParsed?.preferred_username ?? kc.tokenParsed?.email ?? null)
          : null,
      error,
      login,
      logout,
      getAccessToken,
    }),
    [status, error, kc, login, logout, getAccessToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
