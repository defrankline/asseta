import { createContext } from 'react';

export type AuthStatus = 'initializing' | 'authenticated' | 'unauthenticated' | 'error';

/** Outcome of the Keycloak "update password" action, reported once after the redirect back. */
export type PasswordChangeOutcome = 'success' | 'cancelled' | 'error';

export interface AuthContextValue {
  status: AuthStatus;
  /** Keycloak subject (`sub`) of the signed-in user. */
  subject: string | null;
  username: string | null;
  error: string | null;
  login: () => void;
  logout: () => void;
  /**
   * Opens Keycloak's own password page (application-initiated action UPDATE_PASSWORD; Keycloak asks for the
   * current password when the sign-in is not recent) and returns to the current page. The app never handles
   * the password.
   */
  changePassword: () => void;
  /** Result of the last password change in this page load, until cleared. */
  passwordChange: PasswordChangeOutcome | null;
  clearPasswordChange: () => void;
  /** Fresh access token (silently refreshed when close to expiry). */
  getAccessToken: () => Promise<string | null>;
  /**
   * Forces a token refresh now, regardless of remaining validity (keycloak `updateToken(-1)`), so
   * Keycloak groups granted since sign-in (e.g. a managed-service mandate) reach the API.
   * Rejects when the refresh fails (interactive login is then started).
   */
  refreshToken: () => Promise<void>;
  /**
   * Registers a listener called after every successful token refresh (silent or forced), e.g. so the
   * realtime connection re-authenticates. Returns the unsubscribe function.
   */
  subscribeTokenRefresh: (listener: () => void) => () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
