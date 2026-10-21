/** Typed, defaulted access to browser-exposed environment variables. */
export interface AppConfig {
  readonly keycloakUrl: string;
  readonly keycloakRealm: string;
  readonly keycloakClientId: string;
  readonly apiBaseUrl: string;
  readonly mapStyleUrl: string;
  /** Sales contact for the public landing page; the demo button is hidden when unset. */
  readonly contactEmail: string | null;
}

function read(value: string | undefined, fallback: string): string {
  return value !== undefined && value.trim() !== '' ? value.trim() : fallback;
}

export const appConfig: AppConfig = {
  keycloakUrl: read(import.meta.env.VITE_KEYCLOAK_URL, 'http://localhost:8080'),
  keycloakRealm: read(import.meta.env.VITE_KEYCLOAK_REALM, 'asseta'),
  keycloakClientId: read(import.meta.env.VITE_KEYCLOAK_CLIENT_ID, 'asseta-web'),
  apiBaseUrl: read(import.meta.env.VITE_API_BASE_URL, '/api/v1'),
  mapStyleUrl: read(
    import.meta.env.VITE_MAP_STYLE_URL,
    'https://demotiles.maplibre.org/style.json',
  ),
  contactEmail: read(import.meta.env.VITE_CONTACT_EMAIL, '') || null,
};
