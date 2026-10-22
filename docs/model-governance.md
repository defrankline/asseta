# Model governance (Release 1)

How machine-learning models are built, approved, deployed, monitored and switched off in Asseta. Design record:
[ADR-007](adr/ADR-007-intelligence-cases-and-governed-ml.md) (DEC-024). Contract: prompt.md R1-H and §7.

**Status at release:** the unsupervised anomaly model runs in **shadow mode only**. On the synthetic demo fleet it
does not pass promotion (correctly stays shadow); on real tenant data there is not yet enough history
(`INSUFFICIENT_DATA`). No model output is shown to tenant users. Deterministic rules (risk signals, meter exceptions,
tracking alerts) are the production detection layer and work without any model.

## 1. Principles

1. **Four separate records** (§7): observed facts (domain rows, never rewritten) · deterministic signals
   (`risk_signal`, `job_exception`, `tracking_alert`) · model predictions (`prediction`) · human decisions
   (`case_outcome`, immutable). There is no "fraud = true" field anywhere.
2. **Predictions never decide.** They cannot penalize staff, deny payment or block jobs, payments or tracking. A
   surfaced prediction can at most join an investigation case with neutral wording ("Unusual machine-week pattern
   compared with this machine's history — needs review"); a human resolves it (`CONFIRMED_ISSUE` / `UNCONFIRMED` /
   `LEGITIMATE_EXPLANATION`).
3. **No score without evidence.** Until data sufficiency and evaluation pass, the state is `INSUFFICIENT_DATA` or
   `SHADOW`, with the reason visible (`GET /api/v1/tenant/ml/status`, tenant Insights page).
4. **Per-tenant only.** Cross-tenant pooled training is OFF: building a dataset from more than one tenant's snapshots
   raises an error (`backend/src/asseta/ml/datasets.py`; `tests/unit/test_ml_datasets.py::test_mixed_tenants_are_refused`).

## 2. Lifecycle

| Stage | What happens | Code | Tests |
|---|---|---|---|
| Feature definitions | 13 versioned features (spatial, meter, telemetry, finance, behaviour); immutable per version; feature-set hash | `asseta/ml/features.py` | `tests/unit/test_ml_features.py` (incl. `test_feature_set_hash_is_stable_and_changes_on_version_bump`, `test_registry_rejects_duplicate_codes_and_definitions_are_immutable`) |
| Point-in-time snapshots | Weekly `feature_snapshot` rows; a snapshot `as_of` T uses facts whose event **and** recording time are ≤ T; append-only; `source` = `observed` \| `synthetic` | `modules/intelligence/feature_store.py`, `facts.py`; `asseta-ml snapshot` | `tests/api/test_ml_features.py::test_late_recorded_fact_is_excluded_even_if_it_happened_before_as_of`, `::test_weekly_snapshots_from_real_facts_are_append_only`, `::test_snapshots_are_tenant_isolated` |
| Readiness | `SufficiencyCriteria` (defaults: ≥ 5 machines, ≥ 80 machine-weeks, ≥ 8 weeks, plus validation/test rows) → `READY` or `INSUFFICIENT_DATA` with reasons | `asseta/ml/datasets.py` | `tests/unit/test_ml_datasets.py::test_readiness_insufficient_then_ready`, `tests/api/test_ml_governance.py::test_insufficient_data_records_readiness_and_no_model` |
| Training set | Per tenant, temporal split grouped by machine with purge of overlapping windows; manifest (rows, time range, feature-set hash, split boundaries, snapshot source) | `asseta/ml/datasets.py` | `tests/unit/test_ml_datasets.py::test_temporal_split_purges_overlapping_windows_no_entity_time_leakage` |
| Training + MLflow | Robust z-score baseline (median/MAD) and IsolationForest candidate (seeded, standardisation fitted on train only); run, metrics, manifest and model artifacts logged to MLflow (Postgres store, MinIO bucket `asseta-mlflow`). If MLflow is unreachable the model is still persisted locally with the outcome recorded | `asseta/ml/baseline.py`, `models.py`, `training.py`, `tracking.py`; `modules/intelligence/ml_training.py`; `asseta-ml train` or `POST /api/v1/platform/ml/tenants/{tenant_id}/train` | `tests/unit/test_ml_models.py`, `tests/unit/test_ml_training.py::test_unreachable_mlflow_still_produces_local_outcome`, `tests/api/test_ml_governance.py::test_unreachable_mlflow_still_persists_the_model` |
| Evaluation | Candidate vs baseline on held-out time folds with deterministic, labelled injected anomalies; `PromotionCriteria`: recall lift ≥ 0.05, alert rate ≤ 0.05 at the calibrated 98th-percentile threshold, recall std across folds ≤ 0.2, ≥ 5 injected anomalies, data `READY`. Result stored as `model_evaluation` with pass/fail and reasons | `asseta/ml/evaluation.py` | `tests/unit/test_ml_evaluation.py` (`test_promotion_passes_when_candidate_beats_baseline_within_limits`, `test_promotion_fails_with_specific_reason`, `test_promotion_requires_ready_data`) |
| Governance record | `model_version` status graph `TRAINED → EVALUATED → APPROVED → DEPLOYED_SHADOW \| DEPLOYED_ACTIVE → RETIRED`, or `DISABLED`; the same transition graph is enforced in code and by a DB guard | `modules/intelligence/ml_models.py`, `ml_lifecycle.py` | `tests/unit/test_ml_governance_rules.py::test_db_guard_and_code_share_one_transition_graph`, `tests/api/test_ml_governance.py::test_lifecycle_rules` |
| Deploy / rollback / disable | Explicit audited actions with a reason and optimistic `lock_version` (below) | `ml_router.py` | `test_lifecycle_rules` |

## 3. Approvals and who may do what

All lifecycle actions are platform-scoped. Permissions (`modules/intelligence/ml_router.py`):

* `platform.ml.read` — view model versions, evaluations, readiness, settings, predictions, inference audit, drift.
* `platform.ml.manage` — approve, reject, deploy, roll back, disable, retire; run snapshots and training; change the
  hard switch.

Endpoints: `POST /api/v1/platform/ml/models/{id}/{approve|reject|deploy-shadow|deploy-active|rollback|disable|retire}`
(body: `reason`, `lock_version`; `Idempotency-Key` honoured). Preconditions (`MlGovernanceService._preconditions`):

| Action | Refused with |
|---|---|
| Approve / deploy active a model trained on synthetic data | `SYNTHETIC_MODEL` |
| Deploy (shadow or active) or approve without an evaluation | `EVALUATION_REQUIRED` |
| Approve / deploy active when the evaluation did not pass | `EVALUATION_NOT_PASSED` (shadow is still allowed) |
| Deploy active without a recorded approval | `APPROVAL_REQUIRED` |
| Approve twice | `ALREADY_APPROVED` |
| Transition not in the graph | `INVALID_MODEL_TRANSITION` |
| Roll back a non-deployed version / nothing to roll back to | `MODEL_NOT_DEPLOYED` / `NO_PREVIOUS_DEPLOYMENT` |

Deploying a version retires the other deployed version of the same model name. Every action writes an audit event
and `model_approval`/transition rows; `MlModelDeployed` / `MlModelDisabled` events are published. Tenants have no
lifecycle permissions (`tests/api/test_ml_governance.py::test_permissions_and_tenant_isolation`).

Release 1 operating rule: deploy-active requires a passing evaluation on **observed** tenant data and an approval by a
platform owner/admin who records the reason; the live Gate 6 pass showed `Deploy active` refused with `SYNTHETIC_MODEL`
(track.md Gate 6).

## 4. Hard kill switch

`ml_setting.inference_enabled` (single row) — `PUT /api/v1/platform/ml/settings` (`platform.ml.manage`, reason
required, audited). When off, every inference path stops before loading a model, one `SKIPPED` inference-audit row is
written per run, and tenants see that model output is switched off
(`tests/api/test_ml_inference.py::test_hard_switch_off_means_no_inference_and_one_skipped_audit`,
`tests/api/test_ml_governance.py::test_hard_switch_is_audited_and_reaches_tenants`). Disabling a single version
(`/disable`) means it is never scored again (`test_ml_inference.py::test_disabled_model_is_never_scored`).

Use the hard switch first in any incident involving model output; investigate after.

## 5. Shadow policy

* `DEPLOYED_SHADOW` models score in the intelligence worker (hourly) and store predictions with
  `decision_state = SHADOW` and full provenance (feature snapshot refs and time, model name/version, evaluation and
  approval ids, threshold, policy version, contributing features).
* Shadow predictions are **platform-only**: RLS lets tenants read only `SURFACED` rows
  (`migrations/versions/20261022_g6dsec000001_gate6d_predictions_security.py`;
  `tests/api/test_ml_inference.py::test_shadow_predictions_carry_provenance_and_stay_platform_only`).
* An `ACTIVE` model surfaces only calibrated scores above its threshold; below threshold → `BELOW_THRESHOLD`
  (kept for measurement); uncalibrated → `INSUFFICIENT_DATA`. Surfaced rows join a case with neutral wording
  (`test_ml_inference.py::test_active_model_above_threshold_surfaces_a_neutral_case`;
  `tests/unit/test_ml_models.py::test_explanations_never_use_accusatory_language`).

## 6. Monitoring and drift response

* **Inference audit:** every run records outcome, latency and failure reason (`GET /api/v1/platform/ml/inference-audit`).
  Each tenant/model run has its own transaction and a 30 s budget (`TENANT_BUDGET_SECONDS`,
  `modules/intelligence/inference.py`); budget overruns discard that run's predictions and are audited.
* **Drift:** daily PSI per deployed model, training split vs the most recent four weeks of snapshots (10 quantile
  bins + a missing bin, ≥ 30 rows per window; `asseta/ml/drift.py`). Levels: PSI < 0.1 `STABLE`, 0.1–0.25 `WATCH`,
  ≥ 0.25 `DRIFT`. A new `DRIFT` level publishes `MlModelDriftDetected` → platform notification `ML_MODEL_DRIFT`
  to holders of `platform.ml.read` (`modules/intelligence/ml_monitoring.py`;
  `tests/api/test_ml_inference.py::test_drift_is_stable_on_the_training_distribution_and_flags_a_shift`).
  Read: `GET /api/v1/platform/ml/models/{id}/drift`.
* **Drift response runbook** (drift never changes a model automatically):
  1. Open the model detail (platform Models page): which features drifted, their PSI, the time windows.
  2. Check for a data/pipeline cause first (new machines, tracker swaps, a policy change, missing snapshots,
     a feature version bump) — fix the data, not the model.
  3. If the model is `DEPLOYED_ACTIVE` and drift is real, `disable` (or `rollback` to the previous version) with a
     reason; if many models are affected, use the hard switch.
  4. Retrain on the recent window (`asseta-ml train` / `POST …/train`), evaluate against the baseline, and go
     through approval again. A shadow model with drift may stay in shadow while investigated.
  5. Record the decision in the audit reason; note it in track.md if it affects acceptance evidence.

## 7. Data protection

* Training, snapshots and predictions are tenant-scoped with FORCE RLS; snapshots and predictions are append-only for
  the application role (`tests/api/test_intelligence_isolation.py::test_intelligence_isolation_and_immutability`).
* No pooled cross-tenant training (§7); any future pooled learning needs explicit authorization, legal basis and
  de-identification and is backlog, not R1.
* All R1 features are machine-week aggregates (entity `MACHINE`, e.g. meter hours, engine hours, idle ratio, km
  travelled, minutes outside geofence, litres per meter hour, expense total); no free text, photos or personal
  contact data enter the feature matrix, and no model produces a person-level score.
* Model bundles are stored in the platform-private area of the evidence bucket and MLflow artifacts in the
  `asseta-mlflow` bucket; neither is exposed through presigned URLs to tenants.

## 8. Synthetic data rules

* `asseta-ml demo` (development only; refuses outside `ASSETA_ENVIRONMENT=development` —
  `tests/api/test_ml_demo.py::test_demo_command_refuses_outside_development`) writes snapshots with
  `source = synthetic` under a separate model name.
* Real training, inference of real models and tenant insights read `observed` snapshots only
  (`test_ml_demo.py::test_demo_runs_shadow_inference_on_marked_synthetic_data_only`).
* A model whose manifest says `snapshot_source = synthetic` can never be approved or deployed active
  (`SYNTHETIC_MODEL`). Synthetic results are never quoted as product performance.

## 9. Fallback behaviour

If MLflow, MinIO, a model artifact, the intelligence worker or Kafka is unavailable: jobs, payments, sync and
tracking are unaffected; deterministic rules keep running; predictions are simply absent and the reason is recorded
(`tests/api/test_ml_inference.py::test_artifact_failures_are_audited_and_deterministic_rules_keep_running`).
Model inference is never in a request path and never on a mobile device.

## 10. On-device OCR (the other R1 ML component)

* Runs fully offline on the phone: ML Kit text recognition v2 (Android) and Apple Vision (iOS), plus a shared
  geometric pipeline / seven-segment decoder. No remote OCR.
* Governed by the corpus in `contracts/fixtures/ocr` (24 synthetic images, 17 `must_read` / 7 `fallback_ok`;
  acceptance ≥ 90 % must_read and **0 confident wrong reads** per platform) and the shared parse spec
  (`parse_cases.json`). Measured results and history: [ml-ocr-metrics.md](ml-ocr-metrics.md).
* OCR confidence is never proof of authenticity: the original photo is immutable and content-addressed; manual
  corrections raise `MANUAL_CORRECTION`, low confidence raises `LOW_OCR_CONFIDENCE`, and the override audit report
  (`GET /api/v1/tenant/insights/manual-overrides`) lists every override for review.
* A change to an OCR engine, pipeline or confidence threshold must re-run the corpus on both platforms and keep
  0 confident wrong reads before release.
* **Open:** real dashboard photos with permission to use them (EXT-05). Until they are provided and measured, OCR
  accuracy claims apply to the synthetic corpus only.
