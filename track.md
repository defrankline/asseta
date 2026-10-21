# ASSETA — RELEASE 1 IMPLEMENTATION TRACKER

**Scope authority:** `prompt.md` (FROZEN). **Enhancements:** `backlog.md` only.  
**Last update:** 2026-10-21 (session 1: Gates 0–1 verified locally; Gate 2 backend + real Traccar E2E verified; Gate 2 UI next)  
**Overall status:** IN PROGRESS  
**Gate in progress:** Gate 4 — sync backend done; native Android + iOS supervisor field apps next. Gates 1–3 await a live browser walkthrough.  
**Owner:** Implementation agent; final scope decisions by Asseta Platform Owner.

## Rules for maintaining this file

- Update this file *after each material code/test change*, not only at the end of a session. Do not mark a task DONE without verified evidence (test command/results and relevant paths).
- Status values: `NOT STARTED`, `IN PROGRESS`, `BLOCKED`, `DONE`, `FAILED TESTS`.
- Every task includes implementation evidence, tests and unmet acceptance criteria; state blockers honestly.
- Never add features to `prompt.md` or mark backlog requests as Release 1 without explicit owner-approved scope change.
- Maintain the smallest next executable action. If something is blocked by external hardware/secrets, continue an independent in-scope task.
- A task can be `DONE` only after its end-to-end acceptance criteria pass; "files created" is not enough.

## Scope freeze register

| ID | Decision | Status |
|---|---|---|
| S-001 | Asseta is multi-tenant SaaS; platform owner controls tenant subscription pricing | FROZEN |
| S-002 | Subscription billing per DISTINCT subscribed tracked machine (min 1 active paying), monthly or yearly, negotiated tenant rates | FROZEN |
| S-003 | Tenant equipment-hire financial ledger distinct from platform subscription billing | FROZEN |
| S-004 | Python/FastAPI, PostgreSQL/PostGIS, Kafka, Redis, React/strict TS/MUI/Tailwind/Formik/Yup/Axios | FROZEN |
| S-005 | Native Android Kotlin AND native iOS Swift supervisor and owner apps | FROZEN |
| S-006 | Each machine has plug-and-play GPS/telematics adapter; Traccar gateway first | FROZEN |
| S-007 | Owner-controlled AUTO/MANUAL independently for opening/closing readings; all captures attempt GPS | FROZEN |
| S-008 | Genuine mobile offline capture/sync; encrypted local storage; independent machine tracker | FROZEN |
| S-009 | ML is core architecture; production rules + governed learning, no fabricated risk scores | FROZEN |
| S-010 | No scope growth; add ideas to backlog.md | FROZEN |

## Release gate status

| Gate | Milestone | Status | Evidence / acceptance |
|---|---|---|---|
| 0 | Foundations, infrastructure, security and CI | DONE | All Gate 0 items verified locally and on hosted CI run 39582358460 (backend, web, Android, iOS all green) at commit 6857129. |
| 1 | Commercial platform SaaS, per-asset subscription billing | IN PROGRESS | All items implemented + tested locally: backend, scheduler, platform admin UI (59 web tests, mocked services), tracker-swap no-double-billing (Gate 2 test). Awaiting first hosted CI run (EXT-06 resolved: remote added) and a browser pass against the live stack. |
| 2 | Fleet, telematics and PostGIS geospatial | IN PROGRESS | Backend + photos + tenant access + tenant console UI all implemented and tested (web 112 tests); real Traccar E2E verified. Remaining: live browser walkthrough of the console against the Compose stack (UI so far verified with mocked services). |
| 3 | Jobs, configurable photo/manual meter and GPS capture | IN PROGRESS | Backend + OCR corpus + console UI implemented and tested (API 7 acceptance tests, 9 rule tests, 13 OCR parse/manifest tests; web 165 tests mocked). Remaining: live browser walkthrough; mobile capture is Gate 4. |
| 4 | Android + iOS supervisor offline-first apps and sync | IN PROGRESS | Sync protocol v1 backend DONE + 3 acceptance tests. Supervisor field apps implemented on both platforms (offline queue, all push outcomes, resumable blobs, policy snapshots/offline grant, clock tamper, revocation wipe, OCR + GPS capture), verified: iOS 113 `swift test` + 5 app-hosted, Android 93 JVM + 4 instrumented on emulator. Android OCR now 17/17 must_read on emulator (geometric pipeline + seven-segment decoder, ported from iOS), 0 confident wrong. Hosted CI green (39600636563). Live E2E of both apps' real sync clients vs live backend + Keycloak PASS (`scripts/field-e2e.sh`). **Open:** real meter samples (EXT-05); live E2E covers the opening reading only (START/closing/acknowledgement/COMPLETE covered by unit + server acceptance tests). |
| 5 | Tenant hire finance, payments, fuel, expenses and custody | NOT STARTED | — |
| 6 | Fraud intelligence, MLOps and validated analytics | NOT STARTED | — |
| 7 | Android + iOS owner apps, security/performance and release | NOT STARTED | — |

## Gate 0 — Foundation

- [x] Repository organized: `backend/` (modular monolith + workers), `web/`, `mobile/android/`, `mobile/ios/`, `contracts/`, `infra/`, `docs/`, `branding/`.
- [x] Version-pinned dependencies: `backend/uv.lock`, `web/package-lock.json` (exact versions), `mobile/android/gradle/libs.versions.toml`, `mobile/ios/AssetaKit/Package.resolved`; Compose images pinned by digest. Typed settings (`core/config.py`), `.env.example` with placeholders only, `.env` gitignored.
- [x] Docker Compose (`compose.yaml`): PostGIS (built `infra/postgres`, PG 18.6 + PostGIS 3.6, multi-arch), Keycloak 26.8.0 (realm import), Kafka 4.3.1 KRaft, Redis 7.4, MinIO, `migrate`, `api`, `outbox-relay`, `billing-scheduler`, `web`; Traccar 6.10.0 in `telemetry` profile. Verified: `up -d --build`, readiness all 5 deps `ok`, `scripts/compose_smoke.py` SMOKE OK.
- [x] Alembic migrations `44caeb5fa0e9` (baseline), `b1sec0000001` (FORCE RLS on 15 tables, immutability triggers, grants, sequences, seeds), `0ef6473c842e` (outbox retry schedule). Up→down→up and `alembic check` pass. UUID PKs, audit_event append-only.
- [x] Keycloak authoritative authN+authZ (DEC-005, ADR-001): JWKS verification, group-path grants, startup catalog push + mirror pull, tenant role provisioning. Live test against real Keycloak passes. (`tenant_membership` mirror table exists but is not yet populated — Gate 2 R1-B.)
- [x] OpenAPI `contracts/openapi.json` (+ `--check` drift guard), error envelope, correlation IDs, idempotency keys, web DTOs aliased to generated types (drift fails `tsc`). CI `.github/workflows/ci.yml` green on GitHub Actions run 39582358460.
- [x] Cross-tenant API + direct-SQL RLS tests, health live/ready, README/quickstart, docs (architecture, ADR-001..003, security, api, runbook).
- [x] Native project structures: Android (Kotlin/Compose, Room+SQLCipher, Keystore, AppAuth, 8 modules) and iOS (SwiftUI, AssetaKit, SQLCipher 4.19.0, Keychain, ASWebAuthenticationSession), per-app OIDC redirect schemes, brand icons.

## Gate 1 — Commercial subscriptions

- [x] Platform owner onboarding (Keycloak groups + owner user + agreement + rate v1 + subscription), verification, lifecycle transitions (activate/suspend/reactivate/scheduled cancel), dashboard API (MRR/ARR per currency). — backend
- [x] Effective-dated immutable rate versions (currency, cadence, unit price, minimum, discount, tax, mid-cycle policies, rounding); no backdating.
- [x] Enrollment intervals per distinct machine (partial unique index), billable vs enrolled counts, minimum ≥1 (DB check).
- [x] Idempotent invoice generation (unique per period + advisory lock; 4-thread race test), immutable lines (DB trigger test), catch-up renewal, pending proration charges with preview + audited override.
- [x] Manual payments (record→verify/reject, unique reference, overpayment/currency guards, idempotency replay), credit adjustments, versioned entitlement policy (grace/past-due/suspend/read-only, auto-lift on payment, manual suspension).
- [x] Scheduled billing worker (`asseta-billing-scheduler`): renewals + entitlement evaluation, idempotent re-runs.
- [x] Platform admin UI: dashboard, tenants + onboarding stepper (one-time password dialog), tenant detail (verification, lifecycle, rate versions, enrollments w/ end-preview, pending-charge override, invoice preview/generate), invoices (record payment/credit), payments (verify/reject). `web/src/pages/platform/**`; 59 web tests; BigInt money formatting. Not yet exercised in a browser against the live stack.
- [x] Tracker replacement does not double bill — `test_tracker_swap_keeps_one_billable_asset_and_attaches_late_data_by_event_time`.

## Gate 2 — Fleet GPS/PostGIS

- [x] Fleet registry (R1-B): operating areas, categories, machines (capacity, meter precision, ownership, optimistic concurrency), staff, effective-dated assignments; job sites. Customers belong to Gate 3 jobs.
- [x] Machine photos: S3/MinIO adapter (`core/storage.py`), magic-byte validation, content-hash idempotency, immutable rows, 300 s presigned URLs after RLS-scoped authorization; live MinIO test proves expiry and no anonymous access.
- [x] Tenant users & roles (`identity/access.py`): invite (new or existing Keycloak account), grant/revoke role groups in Keycloak, effective-dated `tenant_membership` mirror (never deleted), last-owner guard; orphan Keycloak tenant groups tolerated by sync.
- [x] Policy engine §5: `policy_version` (platform→tenant→machine/site, field-level overridability, no backdating, immutable), `get_effective_policy` with version stamps recorded on positions/events/alerts.
- [x] Tracker registry: platform-approved models + declared capability matrix; tenant trackers (global external-id uniqueness = anti-spoofing); provisioning REGISTERED→VERIFIED_REPORTING only on real data; capabilities verified only when observed; one open primary per machine; swap; DEC-014 enrollment gate.
- [x] Vendor-neutral `TelemetryObservation` + `TraccarAdapter` (unit-converting, no invented values) + deterministic simulator (`asseta.tools.gps_simulator`, direct + OsmAnd modes).
- [x] Ingestion: gateway key (SHA-256 stored), raw retained, quarantine reasons (MALFORMED, UNKNOWN_DEVICE, TRACKER_INACTIVE, UNASSIGNED, NOT_ENROLLED, CLOCK_FUTURE, TOO_OLD), dedupe on (tracker,event_time), event-time assignment resolution, late flag, implausible-jump quality, latest never overwritten by older data, outbox→Kafka timeline worker.
- [x] PostGIS: monthly RANGE partitions + DEFAULT (`ensure_telemetry_partitions`), GiST + BRIN, geography geofences (polygon/corridor), metre tolerance, route playback, stops, distance, site visits, proximity.
- [x] Status dimensions: reported work (UNKNOWN until Gate 3), observed engine (only verified ignition + fresh data), motion, compliance, connectivity LIVE/RECENT/STALE/OFFLINE/NEVER_REPORTED; never live when stale.
- [x] Alerts: geofence exit, restricted entry, unauthorized movement (operating window, tenant tz), GPS anomaly, tamper, low power, tracker stale/offline (+auto-resolve); deterministic replay supersedes, never deletes.
- [x] Tests: 22 Gate 2 API tests incl. delayed/duplicate/malformed/out-of-order/cross-tenant/spoofing; real Traccar 6.10.0 E2E (`scripts/compose_smoke.py` TELEMETRY OK).
- [x] Tracking requires active billable enrollment (DEC-014); tracker swap keeps one billable asset.
- [x] Gate 2 web UI: fleet map (connectivity-styled markers, never live when stale), machine detail + history playback, machines/enrollment, staff, trackers (declared vs verified, swap), geofence drawing (polygon/corridor), alerts, policies, tenant subscription; lazy-loaded routes; 112 web tests (mocked services). Live browser walkthrough pending.

## Gate 3 — Jobs and meter proof

- [x] Customers, versioned rate cards, contracts, jobs (owner-approved price snapshot: rate, minimum hours, standby treatment/rate, mobilization, discount, tax; RATE_CARD vs NEGOTIATED source), job state machine with per-action permissions (supervisor cannot approve), one active job per machine, work log + customer acknowledgement (idempotent client ids).
- [x] METER_CAPTURE policy (independent opening/closing AUTOMATIC/MANUAL, photo rules, OCR confidence, GPS enforcement HARD/SOFT, accuracy/freshness, tracker window/tolerance, increment limits) with tenant/machine/site overrides; HIRE_BILLING policy (increment, rounding). Offline snapshots enforced via `policy_version_ids`; both stamps recorded.
- [x] Every reading carries the GPS attempt result (FIX/NO_FIX/TIMEOUT/PERMISSION_DENIED/DISABLED, accuracy, location time, provider); contract rejects coordinates without a fix; no-fix → PROVISIONAL+GPS_UNAVAILABLE (SOFT) or REJECTED (HARD).
- [x] OCR fixture corpus: 24 deterministic images (`contracts/fixtures/ocr`, generator `asseta.tools.ocr_fixtures`): 4 display styles (7-segment LCD, mechanical drum with tenths wheel, backlit amber with clock distractor, plain digital) × 6 conditions (normal, dim, glare, blur, rotated, noise); 17 must_read / 7 fallback_ok; acceptance targets ≥90% must_read, 0 wrong confident reads (measured per platform in Gate 4). Shared parse spec v1 (`parse_cases.json`, 12 cases) with Python reference parser — both native apps must pass the same cases. Known risk recorded: drum tenths wheel merges in text OCR → caught by sequence rules. Synthetic only — real samples needed (EXT-05). Original photos: content-addressed, immutable, presigned access.
- [x] Meter rules: decrease, impossible increment vs wall clock, cross-job continuity gap, approved reset (segregation of duties), duplicate image hash, tracker location at same time (±window, accuracy-aware), telemetry engine-hours mismatch when reported, clock skew; exceptions auditable + review (EXPLAINED/CONFIRMED), billing_ready only without open blocking exceptions; captures immutable except supersession (DB guard).
- [x] Tests: `tests/api/test_jobs_meter.py` (6) + `tests/unit/test_meter_rules.py` (9) — all four mode combinations, per-machine override, no-fix/HARD/inaccurate, location mismatch vs no comparison, reused photo, boundaries (OPENING_REQUIRED, CLOSING/ACK required), billable 6.5 h vs meter 8.0 h.
- [x] Gate 3 web UI: customers/contracts, rate-card version history, jobs (rate card vs negotiated), job detail (meter vs billable hours, transitions per permission), readings & evidence (photo on demand, GPS evidence, phone vs tracker map), console capture with real browser geolocation attempt, work log, acknowledgements, meter resets (segregation of duties), exceptions review (neutral wording), METER_CAPTURE/HIRE_BILLING/DEVICE_SYNC policies. Contract gaps found by the UI were closed in the API (rate-card/reset/ack lists, photo_attachment_id, tracker coordinates).

## Gate 4 — Native field applications

- [x] Sync protocol v1 server (`modules/sync`, `docs/offline-sync.md`): device sessions + bounded offline grant + revocation/wipe; bootstrap with METER_CAPTURE policy snapshots (audited `device_policy_snapshot`); global `sync_revision` delta pull with lookback; idempotent dependency-ordered push (ACKED/DUPLICATE/DEFERRED/CONFLICT/REJECTED/QUARANTINED) dispatching to the same domain services as the online API; resumable SHA-256-verified chunked evidence upload; DEVICE_SYNC policy. Tests: `tests/api/test_sync.py`.
- [ ] Android Supervisor application: secure offline auth, Room encryption, camera/GPS/OCR/jobs/expenses/collections.
- [ ] iOS Supervisor application: secure offline auth, encrypted storage, camera/GPS/Vision OCR/jobs/expenses/collections.
- [ ] Local policy snapshots and offline authorization restrictions on both platforms.
- [ ] Idempotent delta sync/outbox/inbox, resumable evidence attachments and conflict UI on both.
- [ ] Airplane-mode, prolonged-outage, device clock manipulation, process death/restart and resumed sync tests.

## Gate 5 — Tenant hire finance

- [ ] Tenant customer invoice/line-item creation from approved billable job hours.
- [ ] Deposits/partial payments/receivables and verified payment statuses.
- [ ] Supervisor cash custody, handovers, expenses, approvals, fuel events, receipts and expense GPS per policy.
- [ ] Machine/job/customer profitability, cash reconciliation and reports.
- [ ] Financial reversal/audit and cross-ledger separation tests.

## Gate 6 — ML, anomaly and investigations

- [ ] Deterministic anomaly rule catalog plus explainable investigation cases.
- [ ] Spatial/telemetry/financial/behavior feature versioning and point-in-time extraction.
- [ ] MLflow experiment runs, model registry, approval/deploy/rollback and governance controls.
- [ ] Shadow anomaly detector + baseline comparison; calibrated promotion criteria.
- [ ] Fuel/utilization/revenue/cashflow baseline analytics with explicit insufficient-data behavior.
- [ ] Offline OCR test corpora, documented metrics and audit of manual overrides.
- [ ] Drift/latency monitoring and safe model-off fallback.

## Gate 7 — Owner apps and release hardening

- [ ] Native Kotlin Owner app: fleet map, drilldown, KPIs, alerts, approvals, stale offline cache.
- [ ] Native Swift Owner app: equivalent high-priority functionality and platform-native quality.
- [ ] Admin console coverage of all R1 workflows, reports, reusable forms, accessibility and responsive design.
- [ ] Notification integration with push/email/SMS adapter behavior and explicit provider config.
- [ ] Backup/restore drill, tenant penetration/isolation tests, telemetry and Kafka failure simulation.
- [ ] Release demos + acceptance evidence for 12 contractual criteria in prompt.md §10.
- [ ] Deployment, operation runbook, GPS commissioning guide, model governance and security docs.

## Integration test evidence log

| Date | Scope/test | Command or test harness | Result | Evidence path / notes |
|---|---|---|---|---|
| 2026-10-21 | Backend unit + API (billing, isolation, payments, entitlements, outbox, scheduler) | `cd backend && uv run pytest -q` (local PG18+PostGIS 3.6, app role `asseta_app`) | PASS 40 passed, 3 skipped (live) | `backend/tests/unit`, `backend/tests/api` |
| 2026-10-21 | Live Keycloak 26.8.0 + Kafka 4.3.1 | `ASSETA_IT_KEYCLOAK_URL=… ASSETA_IT_KAFKA=localhost:29192 uv run pytest -m integration` | PASS 3 passed | `backend/tests/integration` (found & fixed: realm lacked built-in `basic` scope → no `sub`) |
| 2026-10-21 | Lint/types | `ruff check`, `ruff format --check`, `mypy --strict` (86 files) | PASS | `backend/pyproject.toml` |
| 2026-10-21 | Migrations | `alembic upgrade head && downgrade base && upgrade head && alembic check` | PASS | `backend/migrations/versions` |
| 2026-10-21 | Compose stack E2E | `docker compose up -d --build`; `/health/ready`; `uv run python scripts/compose_smoke.py ../.env` | PASS (all deps ok; SMOKE OK, outbox relayed) | `compose.yaml`, `backend/scripts/compose_smoke.py` |
| 2026-10-21 | Web console foundation | `npm run lint/typecheck/test -- --run/build` | PASS 38 tests (7 files) | `web/` |
| 2026-10-21 | Platform admin UI (Gate 1) | `npm run lint/typecheck/test -- --run/build/format:check` (after contract regen) | PASS 59 tests (15 files) | `web/src/pages/platform` |
| 2026-10-21 | Gate 2 backend | `uv run pytest -q` | PASS 69 passed, 3 skipped (live) incl. 18-case privilege audit | `tests/api/test_trackers_ingestion.py`, `test_geospatial.py`, `test_fleet_registry_and_grants.py`, `test_authz_upgrade.py` |
| 2026-10-21 | Real Traccar E2E | simulator (IMEI id) → Traccar 6.10.0 OsmAnd → forward → Asseta → PostGIS → Kafka timeline worker → fleet map | PASS: LIVE, engine ON, state events derived, outbox drained | `scripts/compose_smoke.py` |
| 2026-10-21 | First hosted CI run 39580991361 | GitHub Actions | web PASS, iOS PASS; backend FAIL (`ruff format --check`: migration edited after local check), Android FAIL (`setup-android` preview-license prompt). Fixed: `scripts/ci-local.sh` gate before every commit; Android uses preinstalled SDK + `sdkmanager --licenses`. | `.github/workflows/ci.yml`, `scripts/ci-local.sh` |
| 2026-10-21 | Hosted CI run 39582358460 @6857129 | GitHub Actions | PASS backend, web, Android, iOS | https://github.com/defrankline/asseta/actions/runs/39582358460 |
| 2026-10-21 | Live integrations (Keycloak, Kafka, MinIO) | `uv run pytest -m integration` with live services | PASS 4/4 (found & fixed: orphan Keycloak tenant groups crashed mirror sync) | `tests/integration` |
| 2026-10-21 | Hosted CI run 39584890367 @39b8d20 (Gate 2 UI + Gate 3 backend) | GitHub Actions | PASS backend, web, Android, iOS | https://github.com/defrankline/asseta/actions/runs/39584890367 |
| 2026-10-21 | Gate 2 UI + Gate 3 backend | `scripts/ci-local.sh` | PASS backend 88 passed / 4 live skipped; web 30 files / 112 tests; build | found & fixed: meter service used wall clock instead of injected request clock (skew false positives) |
| 2026-10-21 | Gate 3 UI + Gate 4 sync backend | `scripts/ci-local.sh` | PASS backend 106 passed, 4 skipped; web 41 files / 165 tests; build | `tests/api/test_sync.py`, `web/src/pages/tenant/jobDetail` |
| 2026-10-21 | Migration safety | down→base→up and partial cycles **on a populated DB**; `alembic check` | PASS (fixed data-dependent seed downgrade) | `migrations/versions` |
| 2026-10-21 | Android foundation | `./gradlew assembleDebug testDebugUnitTest lint assembleAndroidTest` | PASS (35+ unit tests; lint clean; instrumented SQLCipher test compiled, not run — no emulator) | `mobile/android/` |
| 2026-10-21 | iOS Supervisor field app (Gate 4) | `swift test`; `xcodebuild` Supervisor/Owner; app-hosted tests on iPhone 17 Pro sim | PASS 113 tests / 27 suites (independently re-run); builds succeed; OCR fixtures 17/17 must_read at ≥0.85, 0 confident wrong | `mobile/ios/AssetaKit/Sources/{AssetaCapture,AssetaSync,AssetaField}` |
| 2026-10-21 | Android Supervisor field app (Gate 4) | `./gradlew assembleDebug test testDebugUnitTest lint assembleAndroidTest`; `connectedDebugAndroidTest` on API 35 emulator | PASS 93 JVM (independently re-run with `--rerun`), lint clean, 4/4 instrumented. OCR **9/17 must_read accepted (target 0.90 NOT met)**, 0 confident wrong reads. Found & fixed: CI ran only `testDebugUnitTest`, skipping pure-Kotlin `core:domain`/`core:sync` tests (now `test` too) | `mobile/android/core/{domain,sync}`, `app/supervisor` |
| 2026-10-21 | Hosted CI run 39600636563 @d84e427 (Managed Service, Gate 4 field apps) | GitHub Actions | PASS backend, web, Android (now incl. pure-Kotlin module tests), iOS | https://github.com/defrankline/asseta/actions/runs/39600636563 |
| 2026-10-21 | Field apps vs live stack (Gate 4) | `scripts/field-e2e.sh` (throwaway Keycloak users; fixture tenant/job; iOS real SyncEngine+URLSession+SQLCipher; Android real engine+OkHttp under Robolectric) | PASS iOS + Android (independently re-run): register → bootstrap → opening reading w/ photo+GPS → blob upload → ACKED → DUPLICATE on resend → exactly one server reading. Found & fixed: Android omitted `platform` from device registration (`encodeDefaults=false`) → every real device would fail to register; fake server now validates like the real one | `backend/scripts/field_e2e_setup.py`, `mobile/*/…/SyncLive*` |
| 2026-10-21 | Android OCR uplift (Gate 4) | `connectedDebugAndroidTest` on API 35 emulator (independently re-run) + full Gradle gate | PASS must_read 17/17 (lcd_7seg 3/3, drum 4/4, amber 5/5, plain 5/5), fallback_ok 5/7, 0 confident wrong; floor 16/17 | `mobile/android/core/domain/.../ocr`, `app/supervisor/capture/MeterOcr.kt` |
| 2026-10-21 | Walkthrough defects | web: company panel now reloads after subscription lifecycle changes (regression test fails without fix); backend: access reason refreshed when level unchanged (`test_access_reason_follows_status_even_when_access_level_unchanged`) | PASS web 197 tests; backend suite green | `web/src/pages/platform/tenantDetail/TenantDetailPage.test.tsx` |
| 2026-10-21 | Managed-service mandates (DEC-018) | `uv run pytest -q` (7 new: Keycloak group alone refused, lifecycle/audit/client revoke + stale token, self-revoke + end reason, scope/membership/staff rules, scheduled/expired, two-person approval under mandate, DB immutability guard; privilege audit +2) | PASS 113 passed, 4 skipped | `backend/tests/api/test_managed_service.py` |
| 2026-10-21 | Managed service vs **real Keycloak** | `compose_smoke.py` mandate flow: MANDATE_REQUIRED → grant → staff listed from Keycloak platform groups → assign (Keycloak group added) → refreshed token works → client sees mandate → end → same token MANDATE_ENDED, fresh token MANDATE_ENDED | PASS `MANDATE OK MSM-2026-0001` | `backend/scripts/compose_smoke.py` |
| 2026-10-21 | iOS foundation | `swift test`; `xcodebuild` Supervisor/Owner; app-hosted tests on iPhone 17 Pro sim | PASS 65 tests; both builds; 2 hosted Keychain/SQLCipher tests | `mobile/ios/` |

## Blockers and external dependencies

| ID | External requirement | Impact | Owner/action | State |
|---|---|---|---|---|
| EXT-01 | Keycloak and third-party gateway credentials for deployed staging | Real online authentication/integrations | Platform owner to provision when needed; local dev instance allowed | NOT REQUESTED |
| EXT-02 | At least one supported tracker, SIM, installation/wiring and vendor documentation | Physical device commissioning | Client/platform owner hardware test | NOT REQUESTED |
| EXT-03 | Mobile signing certificates and store accounts | Public App Store/Play distribution | Platform owner | NOT REQUESTED |
| EXT-04 | Payment/tax policies applicable to tenant subscription invoices | Production invoice compliance | Platform owner/accountant | NOT REQUESTED |
| EXT-05 | Real machine dashboard image samples with allowed test usage | OCR validation across target displays | Client/platform owner; synthetic fixtures usable until provided | NOT REQUESTED |
| EXT-06 | Git remote (GitHub) + Actions runners (incl. macOS) | Hosted CI execution of `.github/workflows/ci.yml` | Remote `defrankline/asseta` added by owner 2026-10-21 | RESOLVED (run 39582358460 green) |
| EXT-02a | Hardware commissioning (Gate 2/7) | Simulator + real Traccar verified; physical device not yet tested | Requires customer tracker/SIM/installation | HARDWARE_VALIDATION_BLOCKED |
| EXT-07 | iOS export-compliance decision (`ITSAppUsesNonExemptEncryption`, SQLCipher) | App Store submission | Platform owner/legal | NOT REQUESTED |

## Decision log

| Date | ID | Decision | Reason | Impact |
|---|---|---|---|---|
| 2026-10-21 | DEC-001 | Initial scope frozen in prompt.md | Prevent never-ending implementation | All gates |
| 2026-10-21 | DEC-002 | SaaS fees negotiated per tracked asset, monthly/yearly | User commercial requirement | Platform billing |
| 2026-10-21 | DEC-003 | Traccar initial gateway, adapter abstraction for later vendors | Practical plug-and-play | GPS integration |
| 2026-10-21 | DEC-004 | ML foundation plus staged model activation | No reliable models without adequate data | Intelligence |
| 2026-10-21 | DEC-005 | **Owner clarification: Keycloak is authoritative for authentication AND authorization.** Keycloak realm holds users, per-tenant Organizations/groups and client roles (composite → permissions). API declares a permission per route, idempotently syncs the permission catalog to the Keycloak client at startup, and enforces signed-token tenant + role/permission claims (deny by default). DB `permission`/`role`/`menu` tables are a synchronized mirror for menus, audit and RLS context — never a parallel grant source. Token subject alone never grants tenant access. | Owner message 2026-10-21 | Identity, all gates |
| 2026-10-21 | DEC-006 | Python 3.13 + sync SQLAlchemy 2/psycopg 3; versions pinned via `uv.lock` | Broadest stable library compatibility; simpler transactional reasoning | Backend |
| 2026-10-21 | DEC-008 | Minimal `fleet.machine` core created in Gate 1 (id, asset code, name, status) because billable enrollment needs durable machine UUIDs; Gate 2 extends it | Dependency order | Gate 1/2 |
| 2026-10-21 | DEC-009 | Tenant isolation = app checks + FORCE RLS with scopes tenant/platform/system; platform scope cannot read tenant business tables; subscription mutations serialized by advisory lock (ADR-002) | Defense in depth; FOR UPDATE needs UPDATE policy | All gates |
| 2026-10-21 | DEC-010 | Billing model per ADR-003: bill in advance at period start; mid-cycle changes only in current period → pending charges (preview, override until invoiced); future-dated cancellation; MRR per currency | §1.2 smallest safe defaults | Gate 1 |
| 2026-10-21 | DEC-011 | API money serialized as decimal strings at storage scale (4 dp); display uses currency minor units | Consistent contract, no floats | All clients |
| 2026-10-21 | DEC-012 | Local dev/tests use host PG18+PostGIS 3.6; Compose uses an equivalent built image (official postgis image has no arm64). Asseta host ports: PG 5433, Kafka 29192, Redis 6380, MinIO 9100/9101 | Collisions with other local stacks; reproducibility | Infra |
| 2026-10-21 | DEC-013 | Per-app OIDC redirect schemes `com.asseta.supervisor` / `com.asseta.owner` on single public client `asseta-mobile` | Avoid callback hijack/chooser when both apps installed | Mobile/Keycloak |
| 2026-10-21 | DEC-014 | Gate 2 rule: tracker assignment activation and telemetry processing for a machine require an active billable enrollment on the ingestion date; platform sees "subscribed vs actively tracking" separately | Prevents tracking unbilled machines (tenant can self-unenroll) | Gate 2 |
| 2026-10-21 | DEC-015 | Template permissions are *offered once* per role group (`role_template_grant`): new permissions from a release reach existing groups; owner removals are respected | Found on live stack: Gate 2 permissions never reached existing roles | Identity, every release |
| 2026-10-21 | DEC-016 | Late/out-of-order telemetry handled by deterministic per-machine timeline replay from event time (Kafka keyed by machine); derived events rebuilt, alerts superseded not deleted | §6 late GPS + idempotent re-evaluation | Gate 2+ |
| 2026-10-21 | DEC-018 | **Managed-service mandates** replace console-mode switching for platform staff (ADR-004): consented (consent reference), time-boxed, client-revocable mandates `MSM-YYYY-NNNN`; named staff get the client's Keycloak role groups, honoured by the API only while the mandate is in force (checked every request; stale tokens refused); every audit event stamped with `mandate_id`; client sees staff + actions | Owner: "what you are doing now is cute but not reliable and secure" — must work like the Managed Service in their other product; §1.1 explicit, audited support access | Identity, all tenant routes, web shell |
| 2026-10-21 | DEC-017 | Traccar is configured via env (CONFIG_USE_ENVIRONMENT_VARIABLES); `DATABASE_REGISTER_UNKNOWN` dev-only; production commissioning registers devices explicitly | Plug-and-play dev, controlled prod | Telemetry |
| 2026-10-21 | DEC-007 | Brand mark: "A" with GPS-pin apex and crawler-track crossbar; Slate `#0F2A3D` / Amber `#F5A300` (`branding/`) | Owner delegated logo design | Web/mobile icons |

## Work session log (append each session)

### 2026-10-21 — Baseline initialized
- **Completed:** Authored `prompt.md`, `track.md` and `backlog.md` specification artifacts.
- **Code written:** None yet.
- **Tests run:** None yet.
- **Open issues:** All implementation gates not started.
- **Next smallest action:** Inspect repo and build Gate 0 scaffold, test PostGIS + Keycloak + API boot and tenant isolation.

### 2026-10-21 — Session 1: Gate 0 foundation + Gate 1 backend
- **Completed:** backend core (config, RLS scopes, error envelope, correlation, idempotency, audit, outbox→Kafka relay), Keycloak-authoritative identity (DEC-005), tenancy onboarding, full platform billing domain + scheduler, migrations, Compose stack, realm import, CI workflow, OpenAPI contract + generated web types, web/Android/iOS foundations, brand logo (`branding/`), docs.
- **Tests run:** see evidence log (backend 40+3 live, web 38, Android 35+, iOS 65 + 2 hosted). All green.
- **Defects found and fixed during verification:** realm import missing built-in scopes (tokens without `sub`); PG18 volume layout; TRUNCATE cascade wiping seeded policy in tests; money scale inconsistency; scheduled vs immediate cancellation.
- **Open issues:** platform admin UI (in progress); hosted CI (EXT-06); `tenant_membership` mirror population (Gate 2 R1-B); Redis rate limiting, device sessions (later gates per §4 R1-J/R1-F).
- **Next smallest action:** finish + verify platform admin UI; then Gate 2 — extend `fleet` (categories, specs, assignments), tracker registry/capabilities, `TelemetryObservation` contract + Traccar adapter + simulator, PostGIS position events.

### 2026-10-21 — Session 1 (cont.): Gate 1 UI + Gate 2 backend
- **Completed:** platform admin UI (agent; verified locally), policy engine, R1-B registry, tracker registry, telemetry contract + Traccar adapter + simulator, ingestion, partitioned PostGIS, geofences, timeline replay, alerts, fleet map/history, connectivity sweeper, workers (timeline, connectivity), gateway bootstrap, real Traccar E2E.
- **Defects found and fixed:** migration re-granted revoked invoice DELETE (caught by test; grants now table-scoped + permanent privilege audit); system-scope write pending across RLS scope switch; DB session timezone leaking into API instants (sessions pinned to UTC); geofence DTO computed from unflushed expression; new release permissions not reaching existing roles (DEC-015); data-dependent seed downgrade; Traccar env key naming / device-id regex.
- **Next smallest action:** confirm CI run 2 green; finish + verify Gate 2 web UI (agent running); then Gate 3 (customers, rental contracts/jobs, meter capture policy + GPS evidence).

## Release 1 completion sign-off

- [ ] Gate 0–7 DONE with evidence.
- [ ] All contractual acceptance scenarios from prompt.md §10 documented PASS.
- [ ] No critical/high security, money integrity, sync or tenant isolation defect open.
- [ ] Physical GPS-device validation status documented accurately (PASS or HARDWARE_VALIDATION_BLOCKED).
- [ ] Native Android and iOS artifacts compile and perform offline test flow.
- [ ] Deployment/restore/incident operational documentation complete.
- [ ] Platform owner explicitly accepts Release 1.
