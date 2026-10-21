# ADR-002 — Tenant isolation: application checks + PostgreSQL FORCE RLS

**Status:** Accepted

Every transaction is bound to a scope via `set_config(..., is_local => true)`:

| Scope | Who | Can see |
|---|---|---|
| `tenant` + `app.tenant_id` | tenant users | that tenant's rows only |
| `platform` | platform console | platform commercial tables (all tenants); **no tenant business tables** |
| `system` | internal workers (outbox relay, migrations seeding) | all rows, explicit and audited in code |

* Tenant business tables (e.g. `machine`): policy `tenant_id = app_tenant_id()` (or `system`).
* Platform commercial tables: platform/system write; tenant `SELECT` own rows only.
* Enrollment/pending-charge/settings: platform or owning tenant.
* `audit_event`: anyone may insert; platform reads only `platform.*`/`billing.*` actions.
* Immutable tables (invoice lines, rate versions, status/entitlement events, credits, audit): `UPDATE/DELETE`
  revoked from `asseta_app` **and** rejected by trigger; issued invoice snapshot columns guarded by trigger.
* `SELECT ... FOR UPDATE` requires the UPDATE policy, so cross-scope serialization of a subscription uses a
  transaction-scoped advisory lock (`BillingRepository.lock_subscription`).
* Identity tables (`app_user`, `role`, `permission`, `menu`) are read before a scope exists and carry no tenant
  business data; they are protected by application logic.
