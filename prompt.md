# ASSETA — RELEASE 1 AGENT IMPLEMENTATION CONTRACT

**Document:** `prompt.md`  
**Status:** FROZEN RELEASE 1 BASELINE  
**Product:** Asseta — AI-native, offline-first heavy-equipment rental, utilization, fleet intelligence and fraud-control SaaS  
**Authority:** This file governs Claude Code, Codex, and any delegated coding agents.  
**Companion files:** `track.md` (execution truth) and `backlog.md` (deferred ideas).

---

## 0. AGENT DIRECTIVE — READ THIS FIRST

You are the principal engineer, solution architect, security engineer, QA lead, and implementation agent for **Asseta Release 1**. **IMPLEMENT THE APPLICATION**, not merely a plan, mockup, design, or endless architectural discussion. Work incrementally and deliver production-minded, testable vertical slices. Preserve decisions in this document. Where a detail is not defined, adopt the smallest safe, configurable implementation consistent with the requirements; document the decision in `track.md` and proceed. Ask the human only for genuinely blocking external secrets, paid accounts, hardware, certification, or irreversible production actions. Never claim an integration is live if it is mocked.

**FIRST ACTIONS IN THE REPOSITORY:**
1. Read `prompt.md`, `track.md`, and `backlog.md` completely.
2. Inspect the repository, tooling, git status, existing code and migrations. Preserve functional pre-existing work.
3. Establish/repair the project scaffold and deterministic local development environment.
4. Create an auditable implementation plan in `track.md`, keeping the Release 1 scope fixed.
5. Execute the first incomplete dependency-ordered slice and test it. **Do not stop after planning.**
6. At each iteration update `track.md` with actual artifacts, tests, blockers, next action; put all scope suggestions only into `backlog.md`.

**ABSOLUTE ANTI-SCOPE-CREEP CONTRACT:**
- This document is the complete authorized functional scope for Release 1. **NO extra modules, client apps, providers, features, rewrites, broad refactors, or speculative enhancements.**
- If an idea is useful but not expressly necessary to satisfy an R1 requirement, record it in `backlog.md` with impact/benefit/dependencies; **do not implement it**.
- Bug fixes, security fixes, required integration seams, migration/test scaffolding and work directly necessary to meet acceptance criteria are in scope. Do not use these exceptions to expand product features.
- The agent must not modify this scope baseline or move backlog items into R1 without explicit written authorization from the platform owner. Track changes only as approved change records.
- Prefer simplest production-suitable architecture. **No Kubernetes, microservices explosion, separate data warehouse, generic workflow builder, arbitrary custom report designer or LLM chatbot in R1.**
- No abandoned placeholders, pretend integrations, "TODO complete later" for in-scope functionality, or untested claims of completion. Mark anything blocked honestly.
- Keep a finite checklist and a testable definition of done. The implementation is complete when **R1 acceptance criteria** pass, not when every conceivable improvement has been built.

---

## 1. PRODUCT AND MULTI-TENANT COMMERCIAL MODEL

Asseta is a **B2B multi-tenant SaaS owned and operated by the Asseta Platform Owner**. A tenant is an independent heavy-equipment owner/company managing 1, 2, 100 or more tracked assets. A tenant manages its own machines, users, supervisors, jobs, customers, rental rates, payments, expenses, tracking policies and alerts, while the **Platform Owner** provisions tenants, negotiates their subscription prices, controls SaaS billing, monitors subscription entitlements and manages global identity/permissions and system operations.

### 1.1 Platform roles and boundaries
- **Platform Owner / Platform Admin:** global tenants, rate agreements, subscriptions, SaaS invoices and payments, plan/asset entitlements, system configuration, approved tracker drivers, governance and audits. No ordinary tenant business-data access by default. Any exceptional audited support access requires explicit authorization and is not an everyday bypass.
- **Tenant Owner:** tenant equipment, GPS devices, users/roles, policies, geofences, customers, contract/rental rules, payments, expense controls, financial dashboards, AI risk review.
- **Tenant Manager/Dispatcher:** authorized assignments, schedules, fleet oversight, approvals under delegated permissions.
- **Tenant Supervisor:** assigned machines/jobs, hour-meter evidence, shift/work events, expenses, collections, GPS evidence and offline sync within policy.
- **Tenant Operator (minimal record/role where needed):** operator identity and assignment; no separate operator mobile application in R1.
- **Tenant Accountant/Finance:** invoicing, collections, expenses, reconciliations, receivables, read-only evidence as permitted.
- Roles are tenant-defined; these are **seeded examples**, not permanent hard-coded role names. Permissions are authoritative, deny by default.

### 1.2 R1 SaaS subscription and asset-based billing — MANDATORY
- **Billing unit:** a **billable tracked asset** associated with a tenant subscription, not the number of users, supervisors, GPS messages, or installed app copies. Each physical machine has a durable UUID; replacing its tracker does **not** create a second billed asset.
- **Minimum:** minimum contracted/subscribed asset count **1** for an active paying tenant; support small and large tenants. Suspended/cancelled tenants can have zero current entitlements without violating historical invoices.
- **Cadence:** **MONTHLY** or **YEARLY**, configured per tenant subscription.
- **Price:** **negotiable per tenant** and stored in effective-dated, versioned, auditable commercial agreements (currency, amount per asset per billing period, cadence, start/end, any permitted negotiated minimum/discount, tax configuration). Do not hard-code a public price or assume every tenant has the same rate. Currency must be configurable; provide TZS as a sensible seeded option, not as a fixed business rule.
- **Counting:** distinct subscribed/tracked machine IDs with effective-dated enrollment and clear states. Owner/platform can see billable count, subscribed count and active tracking count separately. Hardware offline does **not** silently remove an asset from billing or infer deactivation. No double charge on tracker swaps or duplicate devices.
- **Subscription lifecycle:** draft → pending activation → active → past due / suspended → cancelled/expired (implement clear allowed transitions); start/renewal dates, billing anchors, change history and cancellation effective date.
- **Asset add/remove:** authoritatively record when equipment joins/leaves the billable fleet. Configurable policy for mid-cycle changes: proration method and rounding, effective date, renewal-date changes or immediate changes; explicit preview before applying. Provide a documented default policy, editable before invoicing; never silently retroactively rewrite issued invoices.
- **Invoices/ledger:** generate SaaS subscription invoice snapshots with period, distinct assets, unit price, amount, negotiated adjustments, applicable configured taxes, total, paid/remaining balance, immutable issued lines, receipts, credits/adjustments, statuses and audit. Use idempotent generation for the same tenant + period; no duplicate issuance from retries. All monetary computation uses fixed-point decimals, never float.
- **Payment:** initially record/verify platform subscription payments manually with references (cash/bank/mobile-money as selected); preserve adapter seams for later payment gateway integrations. Do **not** claim automatic collection or integrate actual payment providers without credentials/explicit permission.
- **Entitlements:** platform-configurable trial/grace/suspension behavior; deterministic and auditable access rules; do not delete or hide tenant data on nonpayment. Preserve read-only/recovery access according to policies. Existing offline records sync safely on reactivation; suspended or unentitled writes are quarantined/rejected per versioned policy, not silently discarded.
- **Separation:** platform's subscription billing is separate from the tenant's **equipment-hire billing** and customer receivables. Never conflate their ledgers, invoices, customers or payments.
- **Platform reporting:** MRR/ARR-equivalent contracted totals by currency, active tenants, billed asset counts, invoices, outstanding subscription amounts and churn events; do not sum different currencies without defined conversion.

---

## 2. TECH STACK — LOCKED

**Backend:** Python (supported stable version), **FastAPI**, Pydantic v2 DTOs, SQLAlchemy 2.x, Alembic, PostgreSQL + **PostGIS**, **Apache Kafka** for async/domain events, Redis for bounded cache/rate limiting, S3-compatible storage (MinIO locally), Python workers for telemetry/notifications/reconciliation/ML, MLflow for model registry and lifecycle. Prefer current mutually compatible stable versions, pin exact versions in lockfiles and document them. 

**Admin console:** Latest stable compatible **React + Vite + strictly typed TypeScript**, **Material UI**, **Tailwind CSS**, **Formik + Yup + Axios**, React Router; MapLibre GL JS for maps. `strict: true`, no `any`, no `@ts-ignore` to hide failures; validate both compile time and runtime.

**Native Android:** Kotlin, Jetpack Compose, Room/SQLite, SQLCipher or equivalent encryption, CameraX, device location services, bundled offline-capable ML Kit OCR, WorkManager, secure credentials/Keystore.

**Native iOS:** Swift, SwiftUI, encrypted SQLite-backed local storage (choose a maintained appropriate library), AVFoundation camera, CoreLocation, Apple Vision on-device OCR, BGTaskScheduler/background capabilities only as supported, Keychain.

**Identity & authorization:** Keycloak OIDC/OAuth2 for online identity/token issuance plus Asseta tenant-scoped RBAC. Database-backed `users`, `roles`, `menus`, `permissions`, `user_roles`, `role_permissions`, `role_menus` and effective-dated access/tenant membership. Define endpoint-level permission metadata in route declarations and **sync permission catalog on startup** (idempotently); centrally managed permission/menu definitions and tenant-owned role assignments. Token subject alone never grants tenant access. Secure bounded offline sessions tied to provisioned device, revocation freshness and explicit offline restrictions.

**Telemetry:** Traccar as **first supported device protocol gateway** plus Asseta-defined vendor-neutral telemetry adapter contract; MQTT/HTTPS/vendor API adapters only where implemented and tested. Do not independently rebuild a large binary device protocol server. Test with a simulator and at least one real supported device before claiming hardware certification.

**Deployment:** Docker Compose for reproducible development and initial deployment; TLS/reverse proxy, secrets/environment management, logging, metrics, backups and recovery tests. Keep infrastructure vendor-neutral. Avoid Kafka/Redis and external model services in the mobile offline critical path.

---

## 3. NON-NEGOTIABLE SOFTWARE ENGINEERING RULES

1. **Modular monolith** Python API plus separately scalable Kafka consumers/ML workers, not independent feature microservices. Modules have explicit boundaries: `platform_billing`, `tenancy`, `identity`, `fleet`, `tracker`, `telemetry`, `geospatial`, `jobs`, `meter`, `finance`, `expenses`, `approvals`, `fraud_intelligence`, `mlops`, `sync`, `notification`, `reporting`.
2. **Service interfaces + implementations** for domain use cases and repositories; dependency injection; thin routers; business rules belong to services/domain policies, not controllers or components.
3. **Never expose ORM entities to API**: Pydantic request/response DTOs; dedicated mapping; native SQL/interface-like projections allowed for efficient reporting but never leak persistence internals.
4. **No code source file >500 lines** (tests/migrations/fixtures excluded only when reasonably justified); DRY, cohesive modules, no copy-paste Android/iOS business rule drift; shared versioned OpenAPI contract and fixtures.
5. UUID IDs everywhere for domain records and offline operations; UTC instants in storage, display tenant timezone; effective-dated policies; monetary Decimal; no global hard-coded business rates, thresholds, geofence tolerances, approval limits, billing anchors, default statuses, device manufacturers or job billing assumptions. Safe seeded defaults are replaceable configuration with audit/versioning.
6. Use explicit DB constraints, unique indexes, foreign keys, transaction boundaries and migration rollbacks where safe; partition and spatial index telemetry tables; tenant_id on tenant-owned tables with DB-enforced isolation where feasible (RLS as defense in depth); tests for cross-tenant denial.
7. Audit actor, role, tenant, device, source, policy version, before/after, timestamp, reason and correlation ID for sensitive changes. No destructive editing of approved financial records, evidence, meter readings or telemetry; corrections via superseding events, reversals and audit. Immutable original uploaded image with content hash.
8. Configurable approval matrices by tenant and permission, with explicitly audited override authority. Do not create a generic BPM platform.
9. Frontend: atomic reusable components; MUI dialogs for forms (no long inline edit forms), stepper with Review for >3 fields, MUI date/time pickers, reusable async autocomplete, Axios service layer, typed DTOs, Yup/Formik validation, debounced search, server pagination/filter/sort, consistent toast/errors/loading/empty states. All routes and actions permission gated; backend remains authoritative.
10. Every important operation has idempotency keys, correlation IDs and structured error responses; API versioning; OpenAPI generation and client contract validation.
11. Tests first or alongside implementation: unit, integration, contract, end-to-end, tenant isolation, failure/retry, offline and geospatial edge cases. CI checks lint, static types, tests, migrations and build artifacts.
12. External calls are through narrow replaceable adapters, with explicit timeout/retry/backoff/circuit breaker where relevant; never fabricate third-party results.

---

## 4. RELEASE 1 FUNCTIONAL SCOPE — THE COMPLETE AUTHORIZED LIST

### R1-A — SaaS platform owner, tenant provisioning and commercial control
- Platform Owner dashboard: tenants, active/suspended subscriptions, billable assets, contracted monthly/yearly pricing, invoices, collection balances, integration health and audit.
- Tenant onboarding: verified company record, timezone, currency, contact, initial owner, subscription agreement (min 1 asset), selected cadence and negotiated rate; tenant provisioning with Keycloak identity mapping.
- Subscription enrollment, billable-asset lifecycle, mid-period changes, renewal, invoices, payments and suspension/grace behavior as §1.2.
- Clear multi-tenant authorization and platform-tenant boundary.

### R1-B — Tenant administration and equipment registry
- Tenant/branch or operating-area info (minimal locations, not a large organization ERP), customers, job sites, machine categories and individual assets; manufacturer/model/serial, meter precision, photos, capacity, status, ownership/assignment.
- Supervisors/operators and role/permission assignments; machine-to-operator/supervisor effective dates.
- Versioned tenant + per-machine configuration overrides for GPS/meter/billing/expense/alerts.

### R1-C — Plug-and-play machine-mounted GPS and telematics
- Device registry, unique external IDs, manufacturer/model, adapter/gateway, credentials reference, SIM/connectivity metadata where necessary, capability matrix, provisioning state and effective-dated one-active-primary-tracker-per-machine assignment (additional sensor records allowed only where needed).
- Initial **Traccar gateway** integration with a normalized `TelemetryObservation` schema; simulator; testable device adapter interface for adding future vendors without changing downstream modules.
- GNSS coordinates, accuracy if supplied, event time, ingestion time, speed, heading, ignition/engine-hour/fuel/power/tamper if supported; raw payload securely retained or referenced; dedupe, authentication, quarantine invalid inputs.
- Tracker offline buffering/replay supported by timestamp-correct ingestion (actual buffering depends on hardware); missing/stale communications and battery/power alerts; live vs last-known map status.
- Never assume any sensor capability exists merely because a vendor advertises it; capability gates are explicit. Distinguish installed hardware from verified reporting.

### R1-D — PostGIS-first fleet location and spatial intelligence
- PostgreSQL/PostGIS point trajectories and jobsite geofence polygons/corridors; proper `geometry(Point,4326)`, geography/metre-aware calculations, GiST indexes and time partitions for high-volume events.
- Fleet command map for owners/admins: near-live or last-known machine positions, last-seen age, location/source/accuracy, current assignment, status evidence, tracker health, available alerts.
- Geofence entry/exit/tolerance alerts, unauthorized movement, site proximity, time-in-location, travel/stop timeline, historical route playback and filterable machine history.
- Machine operational status modeled as separate dimensions: reported work status, sensor-observed state (engine/motion), location compliance and connectivity; `UNKNOWN` where evidence insufficient; do not infer digging/working from GPS alone.
- Compare supervisor phone location at meter capture with machine tracker **at the same observation time**, allowing accuracy/freshness windows; never compare unrelated or stale points as proof.

### R1-E — Contracted equipment rental jobs and hour-meter capture
- Customer contracts/jobs: machine, site, supervisor, effective dates, owner-approved hourly price, minimum hours, included/excluded standby/idle, mobilization, taxes/discounts where configured, job authorization states.
- **Independent owner-configured `AUTOMATIC` or `MANUAL` reading for both OPENING and CLOSING**; global default with per-machine overrides; version-stamped policy and offline enforcement. Automatic: in-app camera photo + on-device OCR; manual: numeric input and optional/required photo according to policy. Same downstream validation/calculation for either method.
- **Every reading, AUTOMATIC or MANUAL, must attempt a fresh GPS fix and preserve location capture result** (lat/long, accuracy metres, source, captured_at, location age, provider state, device). **No valid GPS = provisional exception**, never counterfeit coordinates; configurable hard/soft policy for subsequent review, allowing safe field continuity.
- Bind reading to machine, job, tenant, supervisor, capture mode, raw photo hash/reference if present, original OCR output, confidence/verification state, mobile local ID, device timestamp and server receive time.
- Calculate elapsed meter hours using configured display precision and rollover/replacement workflows (meter reset requires approved documented event). **Engine/meter hours ≠ automatically billable hours**. Apply configurable contract rules and approved nonbillable periods.
- Detect reading decreases, impossible increments, continuity gaps across jobs, duplicate/reused images, inconsistent location and telemetry differences; record auditable exceptions rather than automatic fraud verdicts.
- Readings at **every billable job boundary**, not only each day. Job start/stop/complete with supervisor work log, downtime notes and customer acknowledgement (signature or confirmation evidence stored offline; no external customer app).

### R1-F — Offline-first native supervisor apps (Android AND iOS)
- Assigned jobs/machines cached with versioned policies, local encrypted DB, offline provisioned session, camera/photos, GPS capture, hour-meter OCR, manual fallback per owner policies, working sessions, fuel/issues, expenses and collection entries; authenticated sync on restoration.
- Durable local outbox/inbox with client UUID, operation idempotency, dependency ordering, attachment upload resume/checksum, ACK protocol, exponential retry, bounded batch, conflict result, visibility of pending/failed/quarantined items; no record marked synced before durable server ACK.
- Offline contract/rate approval restrictions, trusted policy snapshots, expiry/revocation behavior, local clock tamper alerts, GPS permission denial/failed fix exceptions, background OS location/sync limitations. Android and iOS do not promise impossible always-on tracking; independent tracker provides machine continuity.
- Encrypted PII/evidence in storage and secure credential management, minimal offline permissions and reasonable local retention.

### R1-G — Tenant hire finance, field expenses and accountability
- Tenant customer invoices/receivables from approved billable hours; deposits/advances, partial payments, cash/bank/mobile money recorded with verification status and references; customer balances and statements.
- Supervisor cash custody, handover, approved petty-cash expenses and daily reconciliation: opening cash + collections − approved spending − handovers = outstanding accountability; distinguish claimed payment from verified settlement.
- Fuel purchase/issue/usage logs, expense categories, receipts/photo/GPS as policy requires, approval limits, supplier and machine/job attribution. Basic profitability by machine/job/customer/period from recognized revenue and categorized direct expenses.
- No full GL, payroll, tax engine, payment gateway implementation or third-party ERP in R1. Use proper money ledgers for this scope and preserve integration boundaries.

### R1-H — Fraud controls, analytics and ML-native intelligence
- Production **deterministic detection** of missing authorization, anomalous meter gaps, unreported engine activity where sensors exist, geofence violation, unusual location at capture, GPS/clock anomalies, tracker tamper/offline, missing cash, duplicate receipts and fuel/expense threshold violations.
- Explainable **exception/investigation case management**: severity, linked evidence, assigned investigator, status, notes, resolution, confirmed/unconfirmed/legitimate outcomes; human review. Predictions alone cannot penalize staff, deny payment or brand a person a fraudster.
- ML data foundation from day one: versioned definitions for spatial, meter, telemetry, finance and behavior features; point-in-time correct training set generation; tenant-isolated datasets; reproducible training, eval, registry, approval, deployment, monitoring/drift, rollback, inference provenance with model/version and explainable reasons.
- R1 predictive baseline candidates: statistical/rule baseline for fuel anomaly, asset utilization and cash-flow trend; **unsupervised anomaly model** trained on adequate representative tenant data and measured against baseline before activation. Until sufficient data/evaluation: **shadow mode or `INSUFFICIENT_DATA`**, not made-up scores or "AI detected fraud". Supervised fraud, advanced predictive-maintenance failure models and advanced price optimization are **backlog**, unless separately approved.
- Offline OCR is a real ML component on both native platforms. Include test dataset(s) representing different dashboard formats/lighting and manual correction audit.
- ML cannot block essential jobs/payments/asset tracking if model inference/registry unavailable; bounded async inference and deterministic fallbacks.

### R1-I — Admin console and native Owner apps (Android AND iOS)
- Platform Admin console (platform-only scopes) + Tenant Admin console (tenant-only scopes) in the React app: dashboards, tenant/subscription billing, equipment, tracker onboarding, maps/history, geofences, configurations, assignments, customers/jobs, photos/readings, payments/expenses, approvals, cases, reports and audit.
- Owner native apps: secure login, tenant fleet map/last-known locations, machine drilldown, jobs/financial overview, evidence and alerts, approvals, configurable priority notifications, bounded offline **read-only cached snapshots** clearly marked stale. Owner apps do not implement full tenant administration, subscription negotiation or all console features.
- Server-side filtering/sorting/pagination and export CSV/PDF for essential fleet, job, reading, cash, expense, alerts, subscription and utilization reports. Use shared report DTOs; no arbitrary report builder.

### R1-J — Operations, security, monitoring and quality
- Tenant isolation tests at API, worker, query, storage and ML layer; Keycloak RBAC tests; signed/verified device ingestion; mTLS/TLS where supported; secrets management; rate limits; audit integrity; appropriate consent/notices and retention for employee GPS/location and photos in deployment jurisdiction.
- Backups/restores, migrations, health/readiness, structured logs, metrics, tracing, lag/dead-letter monitoring, documented recovery and incident procedures; timezone and timestamp correctness.
- Automated tests and reproducible staging demo using **synthetic tenants** (1 and 100+ assets), simulated GPS traces, delayed tracker uploads, conflicting offline events, OCR fixtures, pricing variance and ML shadow-mode demonstration.

---

## 5. DETERMINISTIC CONFIGURATION POLICY ENGINE

Configuration hierarchy: `platform safety/integration constraints` → `tenant policy default` → `machine/job/site policy override` (only where specifically allowed). Use typed versioned configuration schemas, effective dates, validation, auditing and a clear resolution API `get_effective_policy(tenant, machine, job, time)`; never scatter magic constants through clients or SQL.

Owner-adjustable R1 settings include meter opening/closing mode; manual photo requirement; confidence/recapture and manual correction review; GPS freshness/accuracy and no-fix handling; tracker reporting intervals when supported; geofence shape/tolerance; tracker stale thresholds; approved sites/operating windows; billing rules/rounding; expense approval thresholds; fuel allowances; cash handovers; user alert delivery/severity; customer payment terms; evidence retention subject to platform legal minimums.

**Commercial prices are platform-owner administered and tenant-negotiated**, NOT editable by ordinary tenant owners. Tenants can set **their own rental hourly rates** separately. Policy modifications must be authenticated, authorized, effective-dated, versioned and synced; offline capture records the policy version applied, and later policy changes do not silently rewrite old accepted events.

---

## 6. OFFLINE SYNC AND CONCURRENCY — REQUIRED DESIGN

- Design a versioned `/api/v1/sync` protocol with bootstrap snapshot, cursor/delta pull, idempotent push and blob transfer. Secure cross-tenant ownership for every object and attachment.
- Device-generated UUIDs, server monotonic revisions, durable outbox plus attachment queue, operation dependencies, deduplication and eventual convergence. Retries must **never duplicate** jobs, hours, invoices, expenses, receipts or cash payments.
- **Server owns final financial, billing and authorization state**; mobile owns original capture evidence. On conflict never silently last-write-wins an approved/financial record; return structured conflict, retain both evidence trails, escalate to review.
- Late tracker GPS must be attached to event-time windows, not incorrectly to upload time; past alerts/reconciliation should be re-evaluated idempotently with updated evidence.
- Track local capture time, server receive time, effective event time, accuracy and clock offset where feasible. Sync and authorization work under offline/online/repeated-outage test scenarios.
- Document failure matrix: network flaps, duplicate delivery, long offline period, lost/stolen phone, expired/revoked device, suspended subscription, deleted/reassigned machine, GPS disabled, Kafka down, object store down and tracker backlog.

---

## 7. MLOPS AND FRAUD SAFETY CONTRACT

- Separate `observed_facts`, `deterministic_exceptions`, `model_predictions`, `human_decisions`; no one field called "fraud=true" inferred from predictions.
- Each inference includes feature snapshot references/time, tenant, machine/job, model name/version, evaluation approval, score if calibrated, contributing signals, threshold/policy version and decision state.
- On-device OCR confidence is not independently proof of authenticity; preserve originals and support review. Avoid remote-only OCR, as field capture must function without internet.
- Train/test splits must be temporal and grouped to avoid leakage across jobs/machines as appropriate; benchmark false positives, calibration, drift, fairness/behavior proxies and feature integrity.
- Store MLflow runs/artifacts in approved storage; explicit deploy approval by platform admin; model rollback and a hard disable switch; shadow models must not generate user-facing accusations.
- Cross-tenant pooled training is OFF by default; tenant isolation, permission/legal basis, deidentification or explicit authorization required before any pooled learning. Prefer per-tenant baselines and global non-personal equipment priors in R1.
- Clear startup behavior with no labeled incidents or training history: deterministic rules work; anomaly model is disabled/shadow/insufficient data and UI says why.

---

## 8. API, ENTITY AND UI CONTRACTS

Deliver versioned OpenAPI + generated/validated typed client contracts. Required major entities (extend fields as necessary **without creating new product modules**):

- Platform: `tenant`, `tenant_settings`, `commercial_agreement`, `tenant_subscription`, `subscription_asset_enrollment`, `subscription_rate_version`, `platform_invoice`, `platform_invoice_line`, `platform_payment`, `credit_adjustment`, `entitlement_event`.
- Security: `user`, `tenant_membership`, `role`, `permission`, `menu`, `user_role`, `role_permission`, `role_menu`, `device_session`, `audit_event`.
- Equipment: `machine`, `machine_category`, `machine_assignment`, `tracker`, `tracker_model`, `tracker_capability`, `tracker_assignment`, `tracker_ingestion_event`, `machine_position_event`, `machine_latest_position`, `machine_state_event`.
- Spatial: `job_site`, `geofence`, `geofence_event`, `machine_movement`, `tracking_alert`.
- Jobs: `customer`, `rental_rate_policy`, `rental_contract`, `job`, `job_activity`, `meter_capture`, `meter_reset_event`, `capture_attachment`, `customer_acknowledgement`, `job_exception`.
- Finance: `tenant_hire_invoice`, `hire_invoice_line`, `customer_payment`, `supervisor_cash_custody`, `cash_handover`, `expense`, `expense_attachment`, `fuel_event`, `approval_request`, `financial_adjustment`.
- Intelligence: `feature_definition`, `feature_snapshot`, `model_version`, `model_evaluation`, `model_approval`, `prediction`, `anomaly_case`, `case_outcome`, `inference_audit`.
- Sync: `client_operation`, `sync_cursor`, `sync_conflict`, `blob_upload_session`, `device_policy_snapshot`.

Specific schema normalization and join tables are implementer choices; these are domain concepts, not orders to create one table per name indiscriminately. Follow migrations and indexing discipline. Every read/write enforces tenant scoping and appropriate permissions.

---

## 9. DELIVERY SEQUENCE — VERTICAL SLICES, NOT PARALLEL CHAOS

Follow sequence, with tested integrated deliverables at each gate. Subtasks and progress recorded in `track.md`.

**Gate 0 — Foundation:** repository structure, pinned toolchain, Compose (Postgres/PostGIS, Kafka, Redis, Keycloak, MinIO, Traccar development integration, API/workers/web), CI, health, authentication, typed API/error envelope, seed fixtures, tenant isolation tests.

**Gate 1 — Commercial SaaS:** platform/tenant boundaries; negotiated per-asset monthly/yearly subscriptions; enrollment, pricing versions, invoices, adjustments, platform payments, entitlements, platform admin UI; test 1 versus 100 assets, mid-cycle changes, renewal and duplicate billing prevention.

**Gate 2 — Fleet + GPS:** machine registry, trackers, vendor-neutral normalization + Traccar adapter/simulator, PostGIS event ingestion, latest-location map, tracker capabilities/health, geofences/history; test live/stale/late/replayed events.

**Gate 3 — Jobs + meter:** customer/job contracts and configurable price; owner-controlled opening/closing automatic/manual methods, GPS-required attempts, evidence, offline OCR fixtures, meter calculations and sensor reconciliation, approval exceptions.

**Gate 4 — Native supervisor offline:** complete Android and iOS field slices with encrypted local DB, GPS, camera/OCR, local policy enforcement, durable sync and attachments. Demonstrate all critical workflows in airplane mode and after reconnection.

**Gate 5 — Revenue and spending:** tenant-hire invoices/receivables, payments, expenses/fuel, supervisor cash handover and reconciliation, approval workflow and profitability.

**Gate 6 — Intelligence:** deterministic fraud controls and case investigation, governed feature pipelines, MLflow lifecycle, shadow/baseline anomaly detection and baseline insights. Distinguish model readiness and disable unvalidated scores.

**Gate 7 — Owner apps + hardening:** Android/iOS owner apps, alerts/approval/read-only offline cache, end-to-end QA, observability, security, backup/restore, performance and demo acceptance.

Keep each gate deployable where possible. No gate is marked done on code existence alone.

---

## 10. TEST MATRIX AND RELEASE 1 ACCEPTANCE GATES

Do not call Release 1 complete unless each of these has passing automated tests and, where applicable, documented hands-on demonstrations:

1. Platform Owner creates two completely isolated tenants: one 1-asset tenant and one 100-asset tenant. Set **different negotiated monthly/yearly prices**, generate correct invoices independently and prevent cross-tenant data access. Change tracker on a machine without double billing.
2. Subscription changes, suspension, reactivation, grace and prorated mid-cycle asset changes behave according to stored tenant policy; issued invoices remain immutable, retries are idempotent and amounts use Decimal.
3. Register machine and supported tracking device; provision/verify device or clearly marked simulator; ingest GNSS into PostGIS and show source, accuracy, latest/last-seen and offline/stale state.
4. Test polygon/corridor geofence, proximity checks, route playback, late and out-of-order telemetry, device reassignment, cross-tenant tracker spoofing and unknown sensor capabilities.
5. Configure auto start + manual end; switch to manual start + auto end; independently enforce by machine and capture policy version. **Every opening and closing reading attempts GPS**; unavailable or inaccurate GPS becomes an explicit auditable exception.
6. Android **and** iOS independently capture hour-meter image on-device offline, extract supported fixture readings, record manual readings, validate, retain evidence/coordinates and apply billing separately from engine time.
7. With phones offline, create jobs/work logs/expenses/collections; reconnect with duplicates, rejected items, conflicts and failed attachment uploads; ensure exactly one accepted effect with all evidence preserved.
8. Supervisor cash collections minus verified handovers and approved expenses reconcile correctly; tenant customer invoices remain separate from platform subscription invoices.
9. Fraud rules produce actionable evidence-backed exceptions; review workflow records a legitimate explanation without branding someone fraudulent. Missing ML training data yields explicit shadow/insufficient-data behavior.
10. Owner/admin fleet map shows working/reported/observed/unknown states accurately, location timestamps, geofence alerts and machine drilldown; does not claim real-time position when data is stale.
11. Authenticate and deny access at every protected endpoint. Test wrong-tenant requests, stale offline policies, role changes, device loss and storage URL access.
12. Full CI, migration/up-down testing in staging where feasible, backup/restore drill, telemetry load check, Kafka restart, API/worker restart, queue backlog recovery, object store disruption and documentation pass.

**Field hardware criterion:** R1 software must include a fully tested supported Traccar integration and demonstrable simulated GPS device. Real-device commissioning remains a separate explicit acceptance check dependent on customer-provided compatible hardware, SIM, connectivity and installation. If unavailable, report `HARDWARE_VALIDATION_BLOCKED`, not `DONE`.

---

## 11. OUTPUTS, TRACEABILITY AND EXECUTION PROTOCOL

Create/maintain these deliverables in this repository:
- `prompt.md` (this immutable R1 contract), `track.md` (gate/task tracker), `backlog.md` (out-of-scope register).
- Full source for Python API/workers; React admin console; native Android supervisor and owner applications; native iOS supervisor and owner applications; Traccar adapter, simulator, infra, migrations, tests, fixtures.
- `README.md`, `docs/architecture.md`, `docs/adr/` for material tradeoffs, `docs/api.md`, `docs/offline-sync.md`, `docs/gps-hardware.md`, `docs/security.md`, `docs/operating-runbook.md`, `docs/release1-acceptance.md`.
- OpenAPI contract, `.env.example` (no secrets), deployment/backup instructions, tested local quickstart, synthetic demo data and a clear hardware commissioning guide.

**Update `track.md` after every meaningful implementation slice**: status, files/migrations/tests created, command outputs/summaries, what works, known limitations/blockers, next smallest action. **Keep every enhancement idea in `backlog.md`**. Never silently mark work complete. Surface substantive decisions and external dependencies clearly to the human while continuing other unblocked tasks.

**Definition of Done:** All in-scope functionality implemented and integrated across specified clients, tested against acceptance gates, deterministic installs, verified tenant isolation/security, release docs ready, no critical unresolved bugs, and real hardware status transparently documented. No deferred backlog item is required for Release 1 completion.

**IMMEDIATE EXECUTION COMMAND:** Inspect this project, establish Gate 0 and proceed to the first testable slice now. Do not respond with only an implementation plan.
