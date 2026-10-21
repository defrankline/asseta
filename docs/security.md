# Security (status at Gate 0/1)

## Identity & access
* Keycloak realm `asseta` is authoritative ([ADR-001](adr/ADR-001-keycloak-authoritative-authz.md)).
  Clients: `asseta-api` (confidential; service account for catalog sync/provisioning), `asseta-web` (public,
  PKCE S256), `asseta-mobile` (public, PKCE S256; per-app redirects `com.asseta.supervisor:/oauth2redirect`,
  `com.asseta.owner:/oauth2redirect`). Direct-access (password) grants are disabled on all committed clients.
* Realm: brute-force protection, password policy (≥12, history 3), 300 s access tokens, refresh-token rotation.
* Bootstrap first platform owner: Keycloak admin console → realm `asseta` → Users → create → Groups → join
  `/platform/platform-owner`. The API maps platform permissions to that group at startup.
* Token checks: RS256/ES256/PS256 via JWKS (cached, kid rotation), issuer = public Keycloak URL
  (`ASSETA_KEYCLOAK_PUBLIC_URL`), audience `asseta-api`, exp/iat/sub required, 30 s leeway.
* Deny by default: routes without a matching permission in the token's role groups return 403. A token subject
  without group grants gets nothing. Platform scope never reads tenant business tables (RLS).

## Data protection
* DB roles: `asseta_owner` (DDL/migrations, not superuser), `asseta_app` (DML only, FORCE RLS) —
  [ADR-002](adr/ADR-002-rls-scopes.md). Immutable financial/audit records enforced by grants + triggers.
* Secrets only via environment (`.env`, never committed; `.env.example` has placeholders). Realm import uses
  `${ASSETA_API_CLIENT_SECRET}` substitution. The onboarding temporary owner password is returned once, never
  stored in the idempotency store, and Keycloak forces a change at first login.
* All Compose ports bind to 127.0.0.1. Deployments must terminate TLS at a reverse proxy
  ([operating-runbook.md](operating-runbook.md)).
* Mobile: SQLCipher-encrypted local DBs with Keystore/Keychain-held keys; no cloud backup of app data.

## Telemetry & evidence
* Ingestion accepts only gateway-authenticated requests (SHA-256 key hash lookup); device identity is globally unique
  per adapter (a tenant cannot claim another tenant's device); unresolvable data is quarantined, never attributed.
* Telemetry positions, policy versions, machine photos and membership history are immutable for the app role.
* Evidence objects: tenant-prefixed, content-addressed, write-once; clients get 300 s presigned URLs only after an
  RLS-scoped authorization check; buckets are private (verified by `tests/integration/test_minio_live.py`).

## Known gaps (tracked in track.md, in scope for later gates)
* Rate limiting (Redis), device sessions/offline session bounds, mTLS for device gateways, `asseta-api` least-privilege via fine-grained admin permissions, consent/retention notices.
