import { createContext } from 'react';

export type AuthStatus = 'initializing' | 'authenticated' | 'unauthenticated' | 'error';

export interface AuthContextValue {
  status: AuthStatus;
  /** Keycloak subject (`sub`) of the signed-in user. */
  subject: string | null;
  username: string | null;
  error: string | null;
  login: () => void;
  logout: () => void;
  /** Fresh access token (silently refreshed when close to expiry). */
  getAccessToken: () => Promise<string | null>;
  /**
   * Forces a token refresh now, regardless of remaining validity (keycloak `updateToken(-1)`), so
   * Keycloak groups granted since sign-in (e.g. a managed-service mandate) reach the API.
   * Rejects when the refresh fails (interactive login is then started).
   */
  refreshToken: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
