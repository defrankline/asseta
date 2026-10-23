import Keycloak, { type KeycloakInitOptions } from 'keycloak-js';
import { appConfig } from '../config/env';

/** Minimal surface of keycloak-js used by the app; lets tests inject a fake. */
export interface AuthClient {
  token?: string | undefined;
  tokenParsed?: { sub?: string; preferred_username?: string; email?: string } | undefined;
  authenticated?: boolean | undefined;
  onTokenExpired?: (() => void) | undefined;
  onAuthRefreshError?: (() => void) | undefined;
  /** keycloak-js calls this after every successful `updateToken` refresh. */
  onAuthRefreshSuccess?: (() => void) | undefined;
  /** keycloak-js reports the outcome of an application-initiated action (`kc_action`) after the redirect back. */
  onActionUpdate?:
    ((status: 'success' | 'cancelled' | 'error', action?: string) => void) | undefined;
  init(options: KeycloakInitOptions): Promise<boolean>;
  login(options?: { redirectUri?: string; action?: string }): Promise<void>;
  logout(options?: { redirectUri?: string }): Promise<void>;
  updateToken(minValidity: number): Promise<boolean>;
}

/** Seconds of remaining validity below which a token is refreshed. */
export const TOKEN_MIN_VALIDITY_SECONDS = 30;

export function createKeycloakClient(): AuthClient {
  return new Keycloak({
    url: appConfig.keycloakUrl,
    realm: appConfig.keycloakRealm,
    clientId: appConfig.keycloakClientId,
  });
}

export function keycloakInitOptions(origin: string): KeycloakInitOptions {
  return {
    onLoad: 'check-sso',
    pkceMethod: 'S256',
    checkLoginIframe: false,
    silentCheckSsoRedirectUri: `${origin}/silent-check-sso.html`,
  };
}
