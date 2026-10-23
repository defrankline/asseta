# Release 1 acceptance evidence (prompt.md §10)

**As of:** 2026-10-22, repository head `863421a` (last fully completed green hosted CI run: 39819001597 @ `fcd210e`;
earlier runs listed in track.md). Release 1 is **not** complete until every row below is `PASS` and the platform
owner accepts it (track.md "Release 1 completion sign-off").

Status meanings: **PASS** — automated tests pass and the applicable hands-on demonstration is recorded.
**PARTIAL** — automated tests pass but a required demonstration or external input is still missing (reason given).
**BLOCKED** — cannot be completed without an external dependency. 

Test references are `file::test` (backend paths relative to `backend/tests/`, web to `web/src/`, mobile to
`mobile/`). "track.md log" refers to the integration test evidence log in track.md.

## Summary

| # | Criterion (short) | Status | Main gap |
|---|---|---|---|
| 1 | Two isolated tenants (1 vs 100 assets), different prices, tracker swap without double billing | PASS | Automated (`test_platform_billing.py`, `test_trackers_ingestion.py`) + live demonstration 2026-10-23 on the Compose stack: [evidence](evidence/acceptance/2026-10-23-criterion-1.md) (`backend/scripts/demo_acceptance_one.py`); tenants left for inspection in the platform console |
| 2 | Subscription changes, suspension, grace, proration, immutable invoices, idempotency, Decimal | PASS | — |
| 3 | Register machine + tracker, simulated device, GNSS into PostGIS, source/accuracy/stale | PASS (simulator) | Real device: see hardware row |
| 4 | Geofences, proximity, playback, late/out-of-order, reassignment, spoofing, unknown capabilities | PASS | — |
| 5 | Independent AUTO/MANUAL opening/closing per machine, GPS attempt on every reading | PASS | — |
| 6 | Android **and** iOS on-device OCR offline, manual readings, evidence, billing ≠ engine time | PARTIAL | Real dashboard samples (EXT-05); OCR measured on synthetic corpus only |
| 7 | Offline phones: jobs/logs/expenses/collections; duplicates, rejections, conflicts, failed uploads → one effect | PARTIAL | No recorded airplane-mode run on physical phones; live E2E covers the opening reading + finance ops |
| 8 | Cash reconciliation; tenant invoices separate from platform invoices | PASS | — |
| 9 | Evidence-backed fraud exceptions, neutral review, shadow/insufficient-data ML | PASS | — |
| 10 | Fleet map states, timestamps, geofence alerts, drilldown, never claims stale as live | PARTIAL | Console PASS; signed-in live walkthrough of both native Owner apps pending |
| 11 | Deny at every protected endpoint; wrong tenant, stale policy, role change, device loss, storage URLs | PASS | 301 routes enumerated; Medium hardening findings F-5..F-8 fixed (security.md) |
| 12 | CI, migrations, backup/restore, telemetry load, Kafka/API/worker restart, backlog, object-store outage, docs | PARTIAL | All 6 drills PASS; hosted CI green on 7fe05f8 (contains 7E + security fixes; run 39925192479); no staging environment |
| HW | Field hardware criterion (real tracker commissioning) | **HARDWARE_VALIDATION_BLOCKED** | Needs customer tracker, SIM, installation (EXT-02/EXT-02a) |

---

## 1. Two isolated tenants, negotiated prices, no double billing on tracker swap — PASS

**Automated**
* `api/test_platform_billing.py::test_one_asset_monthly_vs_hundred_asset_yearly` — "Solo Excavation" 1 asset at
  TZS 75,000 MONTHLY vs "Mega Fleet" **100 machines** at TZS 600,000 YEARLY with 10 % discount, 18 % tax, minimum 50:
  independent invoices (75,000.0000 vs 63,720,000.0000, 102 lines), each tenant sees only its own invoices, platform
  MRR per currency.
* `api/test_trackers_ingestion.py::test_tracker_swap_keeps_one_billable_asset_and_attaches_late_data_by_event_time`.
* Cross-tenant denial: `api/test_auth_isolation.py::test_tenant_isolation_api_and_rls`,
  `api/test_finance_isolation.py::test_finance_rls_cross_tenant_platform_denial_and_ledger_separation`,
  `api/test_trackers_ingestion.py::test_spoofing_enrollment_gate_and_provisioning`.

**Hands-on:** `compose_smoke.py` onboards a tenant through the real API + Keycloak and checks the tenant token is
refused on platform routes (track.md log 2026-10-21, `SMOKE OK`); the live platform-owner walkthrough
(2026-10-21) covered onboarding/mandates. **Live demonstration (2026-10-23):** `backend/scripts/demo_acceptance_one.py`
created "Solo Excavation Demo" (1 asset, TZS 75,000/month, VAT 18 %) and "Mega Fleet Demo" (100 assets, TZS
600,000/year, −10 %, VAT 18 %, minimum 50) on the Compose stack, swapped the solo machine's tracker, generated both
first invoices (88,500.00 and 63,720,000.00 TZS; one asset line after the swap) and checked cross-tenant refusal
(404 on a foreign machine id, 403 `TENANT_ACCESS_DENIED` on a foreign `X-Tenant-ID`):
[evidence](evidence/acceptance/2026-10-23-criterion-1.md). Both tenants remain in the stack for inspection.

## 2. Subscription lifecycle, proration, immutability, idempotency, Decimal — PASS

**Automated**
* `api/test_platform_billing.py::test_mid_cycle_add_remove_preview_and_next_invoice`,
  `::test_minimum_commitment_applies`, `::test_backdated_and_out_of_period_changes_rejected`,
  `::test_renewal_catch_up_and_rate_renegotiation`, `::test_invoice_generation_is_idempotent_and_concurrency_safe`
  (4-thread race), `::test_issued_invoice_is_immutable_in_database` (DB trigger).
* `api/test_payments_entitlements.py::test_grace_past_due_suspension_and_reactivation`,
  `::test_manual_suspension_requires_manual_reactivation_and_cancellation`, `::test_payment_record_verify_partial_and_full`,
  `::test_missing_idempotency_key_rejected`, `::test_credit_adjustment_and_currency_mismatch`,
  `::test_platform_payment_two_person_rule`.
* `api/test_billing_scheduler.py::test_cycle_generates_renewals_and_suspends_idempotently`;
  `api/test_platform_commerce.py` (ad-hoc invoices, exactly-once fulfilment, void reversal).
* Unit: `unit/test_billing_pricing.py`, `unit/test_billing_calendar.py`, `unit/test_entitlement_rules.py`
  (Decimal-only money; DEC-011).
* Offline writes while suspended are quarantined, not lost: `api/test_finance_sync.py::test_offline_finance_quarantined_while_read_only`,
  `api/test_sync.py::test_conflict_rejection_quarantine_and_revocation`.

**Hands-on:** live platform console walkthrough 2026-10-21 (subscription lifecycle change; defect "company panel
reloads after lifecycle change" found and fixed with a regression test) and platform payments made two-person by
owner decision (DEC-022 entry, track.md log 2026-10-22).

## 3. Machine + tracker registration, simulated device, PostGIS, source/accuracy/staleness — PASS (simulator)

**Automated**
* `api/test_trackers_ingestion.py::test_spoofing_enrollment_gate_and_provisioning` (REGISTERED → VERIFIED_REPORTING only
  on real data), `::test_ingestion_auth_quarantine_dedupe_and_ordering`,
  `::test_unenrolled_machine_data_is_quarantined_and_tamper_alerts`.
* `api/test_geospatial.py::test_fleet_map_status_dimensions_staleness_and_history`,
  `::test_connectivity_sweeper_stale_offline_and_recovery`; `unit/test_gps_simulator.py`.
* Web: `components/fleet/connectivity.test.tsx` ("never presents stale/offline data as live, even if is_live were true").

**Hands-on:** simulated device → **real Traccar 6.10.0** (OsmAnd) → forward → Asseta → PostGIS → Kafka timeline →
fleet map (`backend/scripts/compose_smoke.py`, `TELEMETRY OK`, track.md log 2026-10-21); demo tenant with 4
simulated trackers via Traccar on the fleet map (live walkthrough 2026-10-21). The simulator is clearly marked;
see the hardware row for real devices.

## 4. Geofences, proximity, playback, late/out-of-order, reassignment, spoofing, unknown capabilities — PASS

**Automated**
* `api/test_geospatial.py::test_geofence_exit_with_tolerance_and_late_data_replay` (polygon + tolerance + late replay),
  `::test_corridor_restricted_area_and_unauthorized_movement` (corridor), `::test_fleet_map_status_dimensions_staleness_and_history`
  (history/playback, nearby), `::test_policy_hierarchy_overrides_and_guards`.
* `api/test_trackers_ingestion.py::test_ingestion_auth_quarantine_dedupe_and_ordering` (duplicates, out-of-order),
  `::test_tracker_swap_keeps_one_billable_asset_and_attaches_late_data_by_event_time` (reassignment),
  `::test_spoofing_enrollment_gate_and_provisioning` (cross-tenant tracker spoofing).
* Unknown capabilities: `test_fleet_map_status_dimensions_staleness_and_history` asserts `observed_engine == "UNKNOWN"`
  when ignition was never verified.
* Web: `pages/tenant/machineDetail/HistoryPlayback.test.tsx`, `components/map/DrawPolygonControl.test.tsx`.

**Hands-on:** geofences and fleet map on the live stack with Traccar-delivered positions (track.md log 2026-10-21;
Gate 6 live pass used the Kilimanjaro telemetry).

## 5. Meter capture policy combinations and GPS on every reading — PASS

**Automated**
* `api/test_jobs_meter.py::test_auto_open_manual_close_full_job_and_billable_hours`,
  `::test_mode_combinations_machine_override_and_violation` (all four combinations, per-machine override, policy
  version), `::test_every_reading_attempts_gps_soft_and_hard_enforcement` (NO_FIX/inaccurate → explicit exception or
  rejection), `::test_location_vs_tracker_at_same_time_duplicate_photo_and_idempotency`.
* Mobile local enforcement: `mobile/android/core/domain/src/test/kotlin/com/asseta/core/domain/capture/CaptureRulesTest.kt`,
  `.../policy/PolicySelectorTest.kt`; `mobile/ios/AssetaKit/Tests/AssetaCaptureTests/CaptureRulesTests.swift`,
  `AssetaSyncTests/PolicyAndClockTests.swift`.

**Hands-on:** Gate 5 browser walkthrough 2026-10-22: start refused `OPENING_REQUIRED`, console opening/closing readings
with real browser geolocation attempt, GPS timeout exception reviewed (track.md log). Field E2E (both apps, live
backend) captures an opening reading with photo + GPS (`scripts/field-e2e.sh`, 2026-10-21).

## 6. Android and iOS on-device OCR offline, manual readings, billing ≠ engine time — PARTIAL

**Automated**
* OCR corpus `contracts/fixtures/ocr` (24 synthetic images): Android
  `mobile/android/app/supervisor/src/androidTest/kotlin/com/asseta/supervisor/MeterOcrFixtureTest.kt` (API 35 emulator)
  **17/17 must_read, 0 confident wrong**; iOS `mobile/ios/AssetaKit/Tests/AssetaCaptureTests/VisionOCRFixtureTests.swift`
  and `mobile/ios/Apps/SupervisorTests/VisionOnDeviceOCRTests.swift` **17/17 must_read, 0 confident wrong**
  ([ml-ocr-metrics.md](ml-ocr-metrics.md)). Shared parse spec: `unit/test_ocr_parse_cases.py`,
  Android `core/domain/.../ocr/MeterReadingParserTest.kt`, iOS `AssetaCaptureTests/OCRParserTests.swift`.
* Billing separate from engine time: `api/test_jobs_meter.py::test_auto_open_manual_close_full_job_and_billable_hours`
  (billable 6.5 h vs meter 8.0 h); manual override audit `api/test_insights.py::test_manual_override_audit_lists_ocr_vs_entered_and_is_tenant_isolated`.

**Hands-on:** live field E2E with the real sync clients of both apps (opening reading with photo + GPS → ACKED →
DUPLICATE on resend → exactly one server reading; track.md log 2026-10-21).
**Missing:** OCR on **real** machine dashboard photos (EXT-05); hands-on capture on physical phones is not recorded.

## 7. Offline phones, reconnect with duplicates/rejections/conflicts/failed uploads → exactly one effect — PARTIAL

**Automated**
* `api/test_sync.py::test_bootstrap_offline_batch_replay_and_exactly_once`,
  `::test_conflict_rejection_quarantine_and_revocation`, `::test_resumable_upload_checksum_and_delta_pull`.
* `api/test_finance_sync.py::test_offline_expense_collection_handover_exactly_once`,
  `::test_offline_finance_quarantined_while_read_only`.
* Device side: iOS `AssetaSyncTests/SyncEngineTests.swift`, `OutboxStateMachineTests.swift`, `FinanceSyncTests.swift`,
  `AssetaStoreTests/OutboxTests.swift`; Android `core/sync/src/test/.../FieldUseCaseTest.kt`,
  `core/domain/src/test/.../sync/SyncRulesTest.kt`, `core/database/src/test/.../OutboxV2DaoTest.kt`.

**Hands-on:** `scripts/field-e2e.sh` against the live stack + Keycloak, both apps, independently re-run: opening
reading, expense with receipt, cash collection, handover → ACKED → DUPLICATE on replay → exactly one effect
(`mobile/android/core/sync/src/test/kotlin/com/asseta/core/sync/SyncLiveTest.kt`,
`mobile/ios/AssetaKit/Tests/AssetaSyncTests/AssetaSyncLiveTests.swift`, `AssetaSyncLiveFinanceTests.swift`;
track.md log 2026-10-21). **Missing:** live E2E covers the opening reading only (START/closing/acknowledgement/
COMPLETE via unit + server tests); no recorded airplane-mode session on physical phones (Gate 4 still IN PROGRESS).

## 8. Cash reconciliation; tenant invoices separate from platform invoices — PASS

**Automated:** `api/test_cash_custody.py::test_multi_day_cash_reconciliation_with_claimed_handovers`,
`api/test_finance_isolation.py::test_finance_rls_cross_tenant_platform_denial_and_ledger_separation`,
`api/test_hire_invoices.py` (3 tests incl. void-as-reversal), `api/test_receivables.py::test_partial_payments_allocations_deposit_claims_and_statement`,
`api/test_expenses.py::test_expense_policy_receipts_gps_auto_approval_and_segregation`,
`api/test_profitability.py::test_profitability_by_machine_job_customer_and_period`.

**Hands-on:** three-person Gate 5 browser walkthrough 2026-10-22: HINV-2026-00001 TZS 1,092,500.00; payment
500,000 claimed → verified by a second person; float 200,000 − verified handovers 150,000 = outstanding 50,000.00
(track.md log; Gate 5 signed off by the platform owner; CI 39749518328).

## 9. Fraud rules, neutral review, shadow / insufficient-data ML — PASS

**Automated:** `api/test_intelligence_cases.py::test_section10_9_evidence_backed_case_resolved_with_legitimate_explanation`,
`::test_segregation_of_duties_and_permissions`; `api/test_intelligence_detectors.py` (7 tests: 6 detectors + linking of existing sources);
`api/test_ml_governance.py::test_insufficient_data_records_readiness_and_no_model`;
`api/test_ml_inference.py::test_shadow_predictions_carry_provenance_and_stay_platform_only`;
`unit/test_ml_models.py::test_explanations_never_use_accusatory_language`; `api/test_insights.py::test_fresh_tenant_gets_insufficient_data_with_what_is_missing`.

**Hands-on:** Investigations walkthrough 2026-10-22 (CASE-2026-00003 resolved LEGITIMATE_EXPLANATION, immutable
outcome), shadow-mode demo (8 SHADOW predictions, none tenant-visible), `Deploy active` refused `SYNTHETIC_MODEL`
(track.md Gate 6; signed off by the platform owner; CI 39760674346, 6073bf9). Governance: [model-governance.md](model-governance.md).

## 10. Fleet map states, timestamps, geofence alerts, drilldown; never stale-as-live — PARTIAL

**Automated:** `api/test_geospatial.py::test_fleet_map_status_dimensions_staleness_and_history`,
`::test_connectivity_sweeper_stale_offline_and_recovery`; web `pages/tenant/fleet/FleetMapPage.test.tsx`
("lists machines, labels stale data as last known…", "shows status dimensions and a last-known warning…"),
`components/fleet/connectivity.test.tsx`; owner apps: Android `app/owner/src/test/.../NavigationAndFleetTest.kt`,
`RoomSnapshotStoreTest.kt`, `core/domain/.../owner/OwnerRulesTest.kt`; iOS `AssetaOwnerKitTests/SnapshotCacheTests.swift`,
`OwnerLogicTests.swift`, `PresentationTests.swift`.

**Hands-on:** console fleet map on the live stack shows last-known positions and an honest "No tracker" (2026-10-21);
Dashboard with stale-data warning (Gate 7B). **Missing:** signed-in live walkthrough of the Android and iOS Owner apps
(Android emulator reached Keycloak sign-in only; track.md Gate 7).

## 11. Authentication and denial at every protected endpoint — PASS

**Existing automated tests:** `api/test_auth_isolation.py::test_health_live_and_unauthenticated_denied`,
`::test_invalid_tokens_rejected`, `::test_tenant_isolation_api_and_rls`, `::test_role_permissions_follow_keycloak_mirror`;
`api/test_managed_service.py` (7 tests: Keycloak group alone refused, revoked/ended mandate refuses a still-valid
token); `api/test_tenant_access.py::test_invite_grant_revoke_history_and_last_owner_guard` (role change);
`api/test_sync.py::test_conflict_rejection_quarantine_and_revocation` (device loss → `DEVICE_REVOKED` + wipe);
`api/test_jobs_meter.py::test_meter_decrease_reset_continuity_offline_snapshot_and_immutability` (offline policy
snapshot); `api/test_machine_photos.py::test_machine_photo_lifecycle_and_isolation` (300 s presigned URL, tenant prefix);
`integration/test_minio_live.py::test_presigned_url_works_then_expires`; `api/test_notification_ws.py`
(WebSocket auth, wrong tenant, FORCE RLS); `api/test_fleet_registry_and_grants.py::test_app_role_lacks_forbidden_privileges`;
`api/test_audit_log.py::test_audit_is_tenant_isolated_api_and_rls`; `api/test_intelligence_isolation.py`;
`integration/test_keycloak_live.py::test_live_keycloak_authn_authz_round_trip`.

**Gate 7E penetration / isolation suite** (`backend/tests/api/test_security_pen_*.py`, route inventory
`backend/tests/support/routes.py`, derived from each route's auth dependencies and cross-checked against OpenAPI, so a
new unclassified route fails the suite). 301 route/method pairs: 198 tenant, 91 platform, 4 self-service, 1 gateway,
1 WebSocket, 6 public (health live/ready, OpenAPI JSON, docs, OAuth redirect, redoc — justified in code).
* `test_security_pen_routes.py::test_inventory_is_complete_and_every_guard_is_in_the_catalog`,
  `::test_unauthenticated_and_forged_credentials_refused_everywhere` (293 protected routes × 6 credential variants → 401;
  gateway without/with wrong key/with a user token → 401), `::test_wrong_missing_or_malformed_tenant_header_refused_on_every_tenant_route`
  (198 × 4 → 403), `::test_platform_and_tenant_boundaries_on_every_route` (tenant token on 91 platform routes → 403;
  platform owner holding a tenant group without a mandate → `MANDATE_REQUIRED` on all 198 tenant routes),
  `::test_every_permission_guard_denies_a_role_lacking_exactly_that_permission` (83 permission guards over 289 routes).
* `test_security_pen_idor.py::test_every_tenant_read_by_id_of_another_tenant_is_not_found` (28 read-by-id routes → 404),
  `::test_every_tenant_write_on_another_tenants_ids_fails_and_changes_nothing` (94 writes),
  `::test_crafted_cross_tenant_writes_are_not_found` (13 crafted writes incl. foreign ids in bodies).
* `test_security_pen_sessions.py::test_presigned_urls_are_short_lived_tenant_scoped_and_keys_server_derived`,
  `::test_real_s3_signer_embeds_expiry_and_no_secret`, `::test_revoked_device_is_refused_on_every_sync_endpoint_and_device_ids_are_user_bound`
  (device loss), `::test_stale_offline_policy_is_refreshed_recorded_and_foreign_snapshots_refused` (stale offline policy),
  `::test_role_revocation_and_permission_removal_apply_to_still_valid_tokens` (role change).
* `test_security_pen_inputs.py` (SQL meta characters in every `q`, junk in every query parameter of 87 GET routes,
  hostile path segments, oversized inputs, oversized sync chunks, CSV formula neutralisation).

Defects found and fixed with tests: F-1 role revoked in Asseta stayed usable on a still-valid token (≤ 300 s) — now
refused on REST and WebSocket; F-2 two list-by-parent routes returned `[]` instead of 404 for another tenant's id (no
data leaked); F-3 NUL bytes in input caused 500 → 422 `INVALID_INPUT`; F-4 sync chunk body was read before the size
check → streamed with a cap. The Medium hardening findings are also fixed ([security.md](security.md)): F-5
per-IP rate limits at the web proxy (`web/nginx.conf`, 429 `RATE_LIMITED`; verified live); F-6 11 MiB body limit
in nginx and an ASGI guard in the API (413 `PAYLOAD_TOO_LARGE`; `test_security_limits.py`); F-7 `statement_timeout`
30 s on the app engine, 300 s for workers (503 `QUERY_TIMEOUT`; `test_security_limits.py`); F-8 the offline policy
snapshot must be issued to the device and valid at capture time, otherwise the capture is held for review with
`POLICY_SNAPSHOT_UNVERIFIED` (`test_offline_policy_snapshot_check.py`). No critical, high or medium finding open.

**Status: PASS** (automated; full backend suite green).

## 12. CI, migrations, drills and documentation — PARTIAL

**CI / migrations:** `.github/workflows/ci.yml` (backend lint/format/mypy, migrations up → down base → up +
`alembic check`, pytest, OpenAPI drift; web gen-api drift, lint, typecheck, tests, build; Android; iOS). Green hosted
runs include 39582358460, 39604757419, 39632725670, 39749518328, 39760674346, 39802785727 (af6df12),
39816880946 (b0133de), 39819001597 (fcd210e). Migration cycles on a populated database (track.md log 2026-10-21).
`scripts/ci-local.sh` mirrors CI. Staging: no separate staging environment exists; migrations are exercised on the
local Compose stack and CI only.

**Documentation:** README, [architecture](architecture.md), [ADR-001..007](adr/), [api](api.md),
[offline-sync](offline-sync.md), [gps-hardware](gps-hardware.md), [security](security.md),
[operating-runbook](operating-runbook.md), [model-governance](model-governance.md), [ml-ocr-metrics](ml-ocr-metrics.md),
this file.

**Drills:**

All six drills PASS on the local Compose stack (2026-10-22); details, timings and what is not simulated in
[evidence/drills/README.md](evidence/drills/README.md); scripts in `scripts/drills/`.

| Drill | Result | Key numbers |
|---|---|---|
| [Backup / restore](evidence/drills/2026-10-22-backup-restore.md) | PASS | 165 tables / 113 843 rows, RLS flags, policies, grants, triggers, alembic version identical; evidence objects SHA-256 verified; RTO 7.8 s; RPO = backup interval (no PITR) |
| [Telemetry load](evidence/drills/2026-10-22-telemetry-load.md) | PASS | 100 machines × 63 positions incl. late/out-of-order/duplicates: 0 lost, 0 duplicated; direct p95 send→stored 0.04 s, →latest 0.54 s; via Traccar burst p95 31 s (single API process) |
| [Kafka outage](evidence/drills/2026-10-22-kafka-outage.md) | PASS | 60 s outage: API 0 failures, outbox drained 9.3 s after restart, all consumers lag 0 in 56 s, 136 redeliveries absorbed |
| [API / worker restarts](evidence/drills/2026-10-22-restart-under-load.md) | PASS | API ready 3.8 s, WebSocket reconnect 6.8 s; 8 services + SIGKILL; 0 lost/duplicated effects |
| [Object-store outage](evidence/drills/2026-10-22-object-store-outage.md) | PASS | 503 envelope, rest of API up, resumable upload completed after recovery |
| [Queue backlog](evidence/drills/2026-10-22-queue-backlog.md) | PASS | 2 060 notification msgs in 12 s; 2 000 late timeline msgs in 145 s; exactly once |

The drills found three defects that were fixed with tests (hot gateway row lock and a pool ↔ threadpool convoy that
hung the API under a Traccar burst; timeline worker one-replay-per-message throughput) — see the evidence README.

**Status: PARTIAL** — drills, local full gate and docs PASS; hosted CI green on 7fe05f8, which contains the Gate 7E
and security changes (all four jobs, run 39925192479); remaining: migration up/down on a staging environment (none exists;
migrations are cycled locally and in CI).

## Field hardware criterion — HARDWARE_VALIDATION_BLOCKED

Software: fully tested Traccar integration (adapter + ingestion tests above) and a demonstrable simulated GPS device
through a real Traccar 6.10.0 gateway (`compose_smoke.py`, demo tenant) — **done**. Real-device commissioning has not
been performed: no customer tracker, SIM or installation has been provided (track.md EXT-02 / EXT-02a). The evidence
required to lift this status is listed in [gps-hardware.md](gps-hardware.md#what-hardware_validation_blocked-means).

## Other open external items affecting acceptance

EXT-05 (real OCR samples), EXT-03/EXT-07 (store signing, export compliance), real FCM/APNs/SMTP credentials
(push/e-mail run with console providers locally), EXT-01 (staging Keycloak/integrations), EXT-04 (tax policy for
subscription invoices).
