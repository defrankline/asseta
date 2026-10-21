# Dev-only Keycloak additions

The committed `realm-asseta.json` contains **no human users and no secrets** (`${...}` placeholders are resolved by
Keycloak from environment variables at import). For local development, `scripts/dev-bootstrap-keycloak.sh` creates:

* user `platform.owner@asseta.local` in `/platform/platform-owner` with a **temporary** password (must change at
  first login), and
* the `asseta-integration-test` confidential client with direct-access grants, used **only** by
  `backend/tests/integration` against a disposable Keycloak. Never create it in staging/production.
