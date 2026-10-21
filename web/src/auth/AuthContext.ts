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
}

export const AuthContext = createContext<AuthContextValue | null>(null);
