/** Typed, defaulted access to browser-exposed environment variables. */
export interface AppConfig {
  readonly keycloakUrl: string;
  readonly keycloakRealm: string;
  readonly keycloakClientId: string;
  readonly apiBaseUrl: string;
  readonly mapStyleUrl: string;
  /** Sales contact for the public landing page; the demo button is hidden when unset. */
  readonly contactEmail: string | null;
  /**
   * Realtime WebSocket endpoint (DEC-022). Defaults to `<api base>/ws` on the page's host
   * (ws:// or wss:// to match the page). The access token is never put in this URL.
   */
  readonly realtimeUrl: string;
}

function read(value: string | undefined, fallback: string): string {
  return value !== undefined && value.trim() !== '' ? value.trim() : fallback;
}

/** `ws(s)://` URL for the realtime endpoint, derived from the API base URL when not configured. */
export function deriveRealtimeUrl(
  apiBaseUrl: string,
  location: Pick<Location, 'protocol' | 'host'>,
  explicit?: string,
): string {
  if (explicit !== undefined && explicit.trim() !== '') return explicit.trim();
  const base = apiBaseUrl.replace(/\/+$/, '');
  if (/^https?:\/\//i.test(base)) return `${base.replace(/^http/i, 'ws')}/ws`;
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${scheme}://${location.host}${base.startsWith('/') ? '' : '/'}${base}/ws`;
}

const apiBaseUrl = read(import.meta.env.VITE_API_BASE_URL, '/api/v1');

export const appConfig: AppConfig = {
  keycloakUrl: read(import.meta.env.VITE_KEYCLOAK_URL, 'http://localhost:8080'),
  keycloakRealm: read(import.meta.env.VITE_KEYCLOAK_REALM, 'asseta'),
  keycloakClientId: read(import.meta.env.VITE_KEYCLOAK_CLIENT_ID, 'asseta-web'),
  apiBaseUrl,
  mapStyleUrl: read(
    import.meta.env.VITE_MAP_STYLE_URL,
    'https://demotiles.maplibre.org/style.json',
  ),
  contactEmail: read(import.meta.env.VITE_CONTACT_EMAIL, '') || null,
  realtimeUrl: deriveRealtimeUrl(apiBaseUrl, window.location, import.meta.env.VITE_REALTIME_URL),
};
