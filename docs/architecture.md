# Architecture (Release 1)

## Shape
* **Modular monolith API** (`backend/src/asseta/modules/*`) + separately scalable **workers** (same image, different
  command). Modules: `identity`, `tenancy`, `platform_billing`, `fleet` (Gate 1 core) — later gates add
  `tracker`, `telemetry`, `geospatial`, `jobs`, `meter`, `finance`, `expenses`, `approvals`, `fraud_intelligence`,
  `mlops`, `sync`, `notification`, `reporting` with the same layering.
* **Layering per module:** thin routers → services (use cases, business rules) → repositories/ORM. Routers return
  Pydantic DTOs only; ORM objects never leave services. Pure domain logic (e.g. `platform_billing/pricing.py`,
  `calendar.py`, `entitlement_rules.py`) has no I/O and is unit-tested in isolation.
* **Cross-cutting core** (`asseta/core`): typed settings, per-request transaction + RLS scope (`db.py`), error
  envelope, correlation IDs, idempotency keys, append-only audit, transactional outbox, Kafka adapter, injectable
  clock, pagination.

## Request pipeline
`CorrelationIdMiddleware` → route dependency `requires(permission, scope)`:
1. verify Keycloak JWT (RS256 via JWKS, issuer, audience `asseta-api`, expiry);
2. parse `groups` claim → platform roles (`/platform/<role>`) or tenant roles (`/tenants/<uuid>/<role>`);
3. tenant routes require `X-Tenant-ID` that matches a tenant group in the token;
4. tenant entitlement (`FULL`/`READ_ONLY`/`BLOCKED`) — READ_ONLY rejects non-GET with `SUBSCRIPTION_READ_ONLY`;
5. permission resolution from the Keycloak-synced mirror; deny by default;
6. `SET LOCAL app.scope/app.tenant_id/app.actor_id` so PostgreSQL RLS enforces the same boundary.

## Data
PostgreSQL 18 + PostGIS 3.6. UUID keys, UTC `timestamptz`, `Numeric(18,4)` money, effective-dated versions.
Migrations: Alembic (`backend/migrations`), run as `asseta_owner`; the app connects as `asseta_app` (no DDL,
FORCE RLS applies). See [ADR-002](adr/ADR-002-rls-scopes.md).

## Events
Domain events are written to `outbox_event` in the business transaction; `asseta-outbox-relay` publishes them
to Kafka (idempotent producer, acks=all, `FOR UPDATE SKIP LOCKED`), marking rows only after broker ACK.
Consumers deduplicate on the `event_id` header. Kafka outages never block API writes.

## Commercial model (Gate 1)
See [ADR-003](adr/ADR-003-subscription-billing.md): negotiated per-tenant rate versions, distinct-machine
enrollment intervals, idempotent immutable invoices, pending proration charges, deterministic entitlements.
