# ADR-001 — Keycloak is authoritative for authentication and authorization

**Status:** Accepted (owner clarification 2026-10-21, DEC-005)

## Decision
* Users, tenant membership and role grants live in Keycloak realm `asseta`.
  * Role groups: `/platform/<role>` and `/tenants/<tenant_uuid>/<role>`; the token carries full group paths
    (`groups` claim, mapper on `asseta-web`/`asseta-mobile`).
  * Permissions are client roles `perm:<code>` on client `asseta-api`, mapped to role groups.
* Each API route declares its permission (`requires("tenant.machine.write", TENANT, ...)`). At startup the API
  idempotently pushes the catalog to Keycloak (`perm:*` roles), seeds platform role groups that have no mappings,
  and pulls group→permission mappings into the DB mirror (`role`, `role_permission`, `permission`, `menu`).
* Tenant onboarding creates the tenant's role groups from seeded templates (owner, manager, supervisor,
  accountant, operator) and the initial owner user. Templates are examples; mappings are editable in Keycloak.
* Request-time checks use only the signed token + mirror; no per-request Keycloak call. Grants/revocations take
  effect at the next token (access token lifetime 300 s).

## Consequences
* The DB mirror is never a parallel grant source; it serves menus, audit attribution and offline policy snapshots.
* Startup fails fast if Keycloak is unreachable (Compose restarts the API until it is ready).
* `asseta-api` service account needs realm-management `manage-users`, `view-users`, `query-groups`,
  `view-clients`, `manage-clients`. `manage-clients` is broader than needed (only its own client roles); tightening
  with Keycloak fine-grained admin permissions is tracked as a hardening task for Gate 7.
* Verified by `tests/integration/test_keycloak_live.py` against a real Keycloak 26.8.0 (catalog push, onboarding,
  real tokens, cross-tenant denial, revocation).
