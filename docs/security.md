# Security (Release 1, Gate 7 status)

Scope: what protects tenant data, devices and evidence in R1, how it is tested, and what is still open.
Every claim cites the code or test that backs it. Results are from the 2026-10-22 pen-test sweep (Gate 7E).

## 1. Threat model summary

| Asset | Main threats | Primary controls |
|---|---|---|
| Tenant business data (fleet, jobs, meter evidence, finance, cases) | another tenant reading or changing it; platform staff browsing it; guessed IDs (IDOR) | token group check + `X-Tenant-ID`, managed-service mandates, permission per route, FORCE RLS, per-route 404 on foreign IDs |
| Platform commercial data (subscriptions, invoices, SaaS payments) | tenant users reaching platform routes | PLATFORM-scope permissions; tenant tokens have none |
| Evidence objects (meter photos, receipts, machine photos) | public bucket access, URL sharing, path manipulation | private bucket, server-derived tenant-prefixed content-addressed keys, 300 s presigned GET after an RLS-scoped lookup |
| Telemetry ingestion | spoofed positions, a tenant claiming another tenant's tracker | gateway key (SHA-256 hash lookup), globally unique device IDs, quarantine of anything unresolvable |
| Field devices (supervisor phones) | lost or stolen phone, a modified client, replayed operations | per-user device sessions, bounded offline grant, revocation with wipe, idempotent operation IDs, SQLCipher at rest |
| Identity | forged or expired tokens, privilege escalation through roles | Keycloak JWKS verification (issuer, audience, expiry), deny by default, permission catalog synced from code |
| ML outputs | accusations from unvalidated models, cross-tenant training | shadow predictions are platform-only, pooled training is off, hard switch ([model-governance.md](model-governance.md)) |

Out of scope for R1: network-level DDoS, compromise of the host or Keycloak, and the hardware security of physical trackers.

## 2. Identity and access

* Keycloak realm `asseta` is authoritative for authentication and authorization ([ADR-001](adr/ADR-001-keycloak-authoritative-authz.md)).
  Clients: `asseta-api` (confidential; service account), `asseta-web` and `asseta-mobile` (public, PKCE S256;
  per-app redirect schemes `com.asseta.supervisor` / `com.asseta.owner`). Direct-access grants are disabled on every
  committed client.
* Realm settings (`infra/keycloak/realm-asseta.json`): brute-force protection; password policy
  `length(12) and notUsername and notEmail and passwordHistory(3)`; 300 s access tokens; 1800 s SSO idle timeout;
  refresh-token rotation (`revokeRefreshToken`).
* Token checks (`modules/identity/tokens.py`): RS256/ES256/PS256 through JWKS with key-ID rotation; the issuer must
  be the public Keycloak URL; audience must be `asseta-api`; `exp`, `iat` and `sub` are required; 30 s leeway.
* Request pipeline (`modules/identity/dependencies.py`): verify the token → upsert the user (`USER_INACTIVE`
  refused) → choose the scope → for tenant routes, `X-Tenant-ID` must match a `/tenants/<id>/<role>` group in the
  token → the managed-service mandate gate → subtract revoked roles → tenant access state (BLOCKED / READ_ONLY) →
  permissions from the Keycloak-synced mirror → `SET LOCAL app.scope/app.tenant_id/app.actor_id` for RLS.
* Every route declares exactly one permission through `requires(code, scope)` or `requires_any(...)`. The catalog
  (`modules/identity/catalog.py`) is pushed to Keycloak and mirrored to the database at startup. A token subject
  without group grants gets nothing.
* Platform staff never enter a tenant through Keycloak groups alone. They need an in-force **managed-service
  mandate**, which is checked on every request, so a stale token is refused once the mandate ends. Every audit event
  under a mandate carries its `mandate_id` ([ADR-004](adr/ADR-004-managed-service-mandates.md)).
* **Role revocation is immediate (new in 7E).** When a role is revoked through Asseta, the API stops honouring it
  on the next request, even from an access token that still carries the group claim
  (`IdentityRepository.revoked_role_paths`). The same rule applies to WebSocket authentication. When permissions are
  removed from a role group in Keycloak, they take effect after the next mirror sync, because the API resolves
  permissions server-side rather than from the token.

## 3. Tenant isolation layers (defense in depth)

| Layer | Mechanism | Evidence |
|---|---|---|
| Token / groups | tenant role only from `/tenants/<id>/<role>` claims that match `X-Tenant-ID` | `test_security_pen_routes.py::test_wrong_missing_or_malformed_tenant_header_refused_on_every_tenant_route` |
| Mandate | platform staff need an in-force mandate; checked on every request | `test_managed_service.py`, `test_security_pen_routes.py::test_platform_and_tenant_boundaries_on_every_route` |
| Permission catalog | one guard per route, deny by default | `test_security_pen_routes.py::test_every_permission_guard_denies_a_role_lacking_exactly_that_permission` |
| Database | `asseta_app` has DML only; FORCE RLS on all 93 public tables in the test database (`relforcerowsecurity`); scopes are tenant, platform or system; the platform scope cannot read tenant business tables ([ADR-002](adr/ADR-002-rls-scopes.md)) | `test_auth_isolation.py::test_tenant_isolation_api_and_rls`, `test_fleet_registry_and_grants.py::test_app_role_lacks_forbidden_privileges`, `test_notification_ws.py::test_force_rls_on_new_tables`, `test_finance_isolation.py`, `test_intelligence_isolation.py` |
| Foreign IDs | lookups run under RLS, so another tenant's ID is "not found" | `test_security_pen_idor.py` (all three tests) |
| Storage | keys `tenants/<tenant>/evidence/<sha256>` and `tenants/<tenant>/machines/<id>/photos/<sha256>`, derived on the server; presigned only after an RLS-scoped lookup | `test_security_pen_sessions.py::test_presigned_urls_are_short_lived_tenant_scoped_and_keys_server_derived`, `tests/integration/test_minio_live.py::test_presigned_url_works_then_expires` |
| Workers | Kafka consumers bind the tenant RLS scope per event (`apply_scope(..., TENANT, tenant_id)`); system scope is used only for routing and outbox | `test_notifications.py` (tenant isolation), `test_intelligence_isolation.py` |
| WebSocket | the first frame carries the token and tenant, then the same tenant, mandate, revocation and permission checks as REST | `test_notification_ws.py::test_wrong_tenant_and_platform_context_refused` |
| ML | per-tenant datasets (`TenantMixingError`; pooled training is off); shadow predictions are platform-only (RLS) | `test_ml_governance.py::test_permissions_and_tenant_isolation`, `test_ml_inference.py::test_shadow_predictions_carry_provenance_and_stay_platform_only` |

## 4. Secrets

* Secrets come only from the environment (`.env`, gitignored; `.env.example` holds placeholders only). The realm
  import substitutes `${ASSETA_API_CLIENT_SECRET}`. FCM and APNs key files are mounted read-only and referenced by
  `*_FILE` variables (`compose.yaml`).
* The onboarding temporary owner password is returned once and never stored in the idempotency store. Keycloak
  forces a change at first login.
* Gateway keys are shown once and stored as SHA-256 hashes (`telemetry/router.py`).
* Clients never receive storage credentials. A presigned URL carries a SigV4 signature, never the secret
  (`test_security_pen_sessions.py::test_real_s3_signer_embeds_expiry_and_no_secret`).
* All Compose ports bind to 127.0.0.1. Deployments must terminate TLS at a reverse proxy
  ([operating-runbook.md](operating-runbook.md)).

## 5. Device and telemetry security

* **Gateway ingestion:** `POST /api/v1/telemetry/traccar` requires `X-Asseta-Gateway-Key`. A missing key, a wrong
  key or a user token all get 401 (`test_security_pen_routes.py::test_unauthenticated_and_forged_credentials_refused_everywhere`).
  Device IDs are globally unique, so a tenant cannot claim another tenant's tracker. Unresolvable data is
  quarantined (`test_trackers_ingestion.py::test_spoofing_enrollment_gate_and_provisioning`). mTLS for device
  gateways is not implemented; Traccar sits on the internal network.
* **Device sessions:** a device registers per user (`X-Device-Id`), and the same device ID presented by another
  user is `DEVICE_NOT_REGISTERED`. The offline grant is bounded by `DEVICE_SYNC.offline_grant_hours` (default 72 h).
  Revocation returns `DEVICE_REVOKED` with `WIPE_LOCAL_DATA` on every sync endpoint (bootstrap, changes, push, blob
  start/chunk/complete) and refuses re-registration
  (`test_security_pen_sessions.py::test_revoked_device_is_refused_on_every_sync_endpoint_and_device_ids_are_user_bound`,
  `test_sync.py::test_conflict_rejection_quarantine_and_revocation`).
* **Offline policy snapshots:** the server issues snapshots with an expiry (`snapshot_validity_hours`) and records
  each one (`device_policy_snapshot`). The next contact delivers the new versions. A capture made under a stale
  snapshot records both the server stamp and the device stamp. Another tenant's policy versions are refused with
  `POLICY_SNAPSHOT_UNKNOWN` (`test_security_pen_sessions.py::test_stale_offline_policy_is_refreshed_recorded_and_foreign_snapshots_refused`).
* **At rest on phones:** SQLCipher-encrypted databases with Keystore/Keychain-held keys; no cloud backup of app data.
* **Evidence:** content-addressed and write-once (`IfNoneMatch="*"`). Images are validated by magic bytes, never by
  the declared type. Database rows are immutable (triggers and grants).

## 6. Penetration test results (Gate 7E, 2026-10-22)

The suite is `backend/tests/api/test_security_pen_{routes,idor,sessions,inputs}.py`, with route inventory in
`backend/tests/support/routes.py`. The inventory is derived from route dependency metadata (`requires` /
`requires_any` closures, `get_claims`) and cross-checked against the OpenAPI document. Any route that has no auth
dependency and is not on the explicit allow-list fails the suite.

**Inventory: 301 route/method pairs.** TENANT 198, PLATFORM 91, SELF 4 (`/me`, push devices), GATEWAY 1,
WEBSOCKET 1, PUBLIC 6. The public allow-list, each with a justification in code: health live and ready, OpenAPI
JSON, Swagger UI, the Swagger OAuth redirect page and ReDoc.

| # | Check | Coverage | Result |
|---|---|---|---|
| i | no credential, malformed bearer, Basic auth, non-JWT, wrong-key-signed and expired tokens → 401 | 293 protected routes × 6 variants (1,758 requests); gateway × 3; public routes → 200 | PASS |
| ii | tenant-A token with tenant-B, unknown, missing or SQL-ish `X-Tenant-ID` → 403 | 198 tenant routes × 4 (792) | PASS |
| iii | tenant token on platform routes → 403; platform owner holding a tenant group but no mandate → `MANDATE_REQUIRED` | 91 × 2 + 198 | PASS |
| iv | for each of 83 distinct guards, a role holding every permission of its scope except that one → 403; the same role with the permission is not refused and no route returns 5xx on random IDs or empty bodies | 289 routes | PASS |
| v | IDOR: B's real IDs under A's owner | 28 GET-by-ID routes → 404; 94 write attempts → none succeed, 28 reads of B unchanged; 13 crafted writes, including cross-tenant foreign keys in bodies → 404 | PASS after fix F-2 |
| vi | presigned URLs: TTL 300 s, tenant-prefixed, server-derived keys (hostile file names ignored), other tenant → 404; real signer embeds `X-Amz-Expires`; live expiry in MinIO | 3 URL kinds | PASS |
| vii | revoked device on all 7 sync endpoints; user-bound device IDs; stale or foreign offline policy; permission removal and role revocation with a still-valid token | as listed | PASS after fix F-1 |
| viii | 9 injection payloads (SQL meta, LIKE wildcards, UNION, NUL, 5,000 chars) in `q` on 49 searchable routes; 7 junk values in every query parameter of 87 GET routes; hostile path segments; 1 MB field; ~2 MB body; >10 MB image; oversized sync chunk and declared size; CSV formula triggers `= + - @ \t \r` | as listed | PASS after fix F-3 |
| ix | rate limiting / payload limits | see findings F-5 and F-6 | GAPS (open) |

### Findings

| ID | Severity | Finding | Status |
|---|---|---|---|
| F-1 | Medium | When a role was revoked through Asseta, the user's still-valid access token (group claim present for up to 300 s) kept full access until it expired. | **Fixed.** The API ignores roles whose mirrored membership is closed with none open again; WebSocket follows the same rule. Test: `test_role_revocation_and_permission_removal_apply_to_still_valid_tokens` (failed before the fix: 200 instead of 403). Roles revoked directly in Keycloak take effect at the next mirror refresh or token expiry. |
| F-2 | Low | `GET /tenant/machines/{id}/trackers` and `GET /tenant/jobs/{id}/meter-captures` answered another tenant's ID with `200 []` instead of 404. No data leaked (RLS), but the behaviour was inconsistent with every other by-ID read. | **Fixed:** a parent lookup returns 404 (`tracker/service.py`, `meter/router.py`). Test: `test_every_tenant_read_by_id_of_another_tenant_is_not_found`. |
| F-3 | Low | A NUL byte (`\x00`) in any text input (`q` on 22 list routes, other query parameters, JSON fields) caused a database `DataError` and an HTTP 500. It was not injectable; the error envelope stayed generic. | **Fixed:** the `DataError` handler returns 422 `INVALID_INPUT` and the transaction rolls back (`core/errors.py`). Tests: `test_sql_meta_characters_in_every_search_box_are_inert`, `test_junk_in_every_query_parameter_never_crashes`, `test_oversized_inputs_are_refused_without_server_errors`. |
| F-4 | Low | `PUT /sync/blobs/{id}/chunks/{n}` buffered the whole request body before checking its size, so one authenticated device could send a very large body. | **Fixed:** the body is streamed with a 256 KiB cap and refused with `BAD_CHUNK` (`sync/router.py::_bounded_body`). Test: `test_sync_chunk_larger_than_declared_is_refused`. |
| F-5 | Medium | **No HTTP rate limiting** on the API: login brute force is covered by Keycloak, but API and gateway request floods are not throttled. The only throttle is SMS per recipient (`sms_rate_limit_per_hour`). | **Open.** Recommended: per-IP and per-subject limits at the reverse proxy (e.g. nginx `limit_req`) in front of `/api/` and the gateway. Redis-backed app limits remain a backlog item. |
| F-6 | Medium | **No global request-size limit** in the API. Upload handlers cap reads at `max_image_bytes` (10 MB), but multipart bodies are spooled before the cap applies, and JSON bodies are unbounded. `web/nginx.conf` sets no `client_max_body_size`, so nginx's 1 MB default applies to console uploads through the web proxy; this may also refuse legitimate photos above 1 MB. | **Open.** Set `client_max_body_size` (about 11 MB) on `/api/` at the deployment proxy; consider an ASGI Content-Length guard. |
| F-7 | Medium | The database app role had no `lock_timeout`, `statement_timeout` or `idle_in_transaction_session_timeout`. Found in the telemetry load drill: one hot row lock let the pool and threadpool exhaust and hung the API, including `/health/ready`. | **Partly fixed by the drill work:** `lock_timeout` 5 s and `idle_in_transaction_session_timeout` 60 s on the app engine; `OperationalError` → 503 `DATABASE_BUSY`; the gateway heartbeat write is throttled and the ingest endpoint commits before FastAPI's response-validation threadpool hop (`tests/api/test_telemetry_gateway_heartbeat.py`; [drill evidence](evidence/drills/README.md)). `statement_timeout` is still unset. Details in the runbook drill evidence. |
| F-8 | Medium | Offline policy snapshot trust: device-supplied `policy_version_ids` are accepted when they resolve to versions visible to the tenant (platform and own tenant). The server does not verify that the snapshot was actually issued to that device or that it was still valid at `captured_at`. A modified client could therefore enforce an older, more lenient version of its own tenant's policy. This is mitigated by both stamps being recorded on every capture (`server|device:Nv`) for review, and foreign versions are refused. | **Open.** Recommended: check against `device_policy_snapshot` (issued to this device, `issued_at ≤ captured_at ≤ valid_until`) and raise a review exception otherwise, rather than rejecting, to keep field continuity. |
| F-9 | Info | The OpenAPI JSON, Swagger UI, `/redoc` and the Swagger OAuth redirect page are public. They expose only the published contract (the same as `contracts/openapi.json`). | Accepted. Optionally block `/redoc` and `/api/v1/docs` at the production proxy. |
| F-10 | Info | Some cross-tenant body references return a "not found or not active" 422 (e.g. `CONTRACT_NOT_ACTIVE`) instead of 404. The code and message are the same as for a non-existent ID, so existence is not disclosed. | Accepted (test allow-list). |

No critical or high findings are open. Existing CSV injection protection (`reports/render.py::safe_csv_cell`) and
LIKE-escaping (`core/search.py`) held under the sweep.

## 7. Known gaps (honest list)

* Rate limiting (F-5) and request-size limits (F-6) depend on deployment proxy configuration that is not yet
  written. `statement_timeout` is unset (F-7).
* The offline snapshot issuance check is not enforced server-side (F-8).
* mTLS for tracker gateways is not implemented. Traccar to API runs on the internal Docker network; device-to-Traccar
  protocols are vendor-dependent and mostly unauthenticated, so device identity relies on IMEI uniqueness plus
  quarantine.
* `asseta-api` uses a broad Keycloak service account; least privilege through fine-grained admin permissions is not
  done.
* Consent and retention notices for employee GPS and photos depend on the deployment jurisdiction and are an owner
  and legal input. Evidence retention is policy-configurable, but no legal minimums are encoded.
* Platform role revocation (`/platform/*`) is still bounded by token expiry (300 s). Tenant roles and mandates are
  immediate.
