# ADR-007 — Intelligence: deterministic signals, investigation cases and governed ML

**Status:** Accepted (DEC-024), 2026-10-22. Implements Gate 6 / R1-H and the §7 MLOps and fraud safety contract.

## Context

prompt.md R1-H and §7 require production deterministic detection, explainable case management with human outcomes,
an ML data foundation (versioned features, point-in-time training sets, tenant isolation), an MLflow lifecycle with
approval/deploy/rollback/disable, a shadow unsupervised anomaly model measured against a statistical baseline, and
baseline insights, with explicit `INSUFFICIENT_DATA` behaviour. Predictions must never penalize, deny payment or brand
anyone. Backlog keeps supervised fraud models (BL-001) and a separate feature platform (BL-020) out of R1.

Much of the deterministic layer already exists and stays where it is: meter exceptions (`job_exception`, 14 types),
tracking alerts (`tracking_alert`), segregation-of-duties signals and the overdue-cash reminder.

## Decision

### Four separate kinds of record (§7)

1. **Observed facts** — the existing domain rows (captures, positions, expenses, fuel, custody). Never rewritten.
2. **Deterministic signals** — explainable rule outputs. Existing sources (meter exceptions, tracking alerts, SoD
   violations) plus new detectors in a new `intelligence` module, written as `risk_signal` rows: rule code + version,
   severity, subject (machine / job / staff member / expense), observed window, evidence JSON (facts and thresholds,
   never conclusions), policy version, dedupe key. New R1 detectors:
   `UNREPORTED_ENGINE_ACTIVITY` (verified ignition on/engine-hours increase with no IN_PROGRESS job on the machine),
   `DUPLICATE_RECEIPT` (same receipt SHA-256 on another expense in the tenant), `FUEL_ALLOWANCE_EXCEEDED`
   (litres per meter hour above the machine/tenant allowance), `EXPENSE_THRESHOLD_EXCEEDED` (category or machine
   spend in a period above the policy threshold), `CASH_NOT_HANDED_OVER` (outstanding custody older/larger than
   policy), `WORK_WITHOUT_AUTHORIZATION` (activity, captures or expenses on a job that was not APPROVED/IN_PROGRESS
   at the time, or by a supervisor not assigned to the machine then). Thresholds live in versioned policy (a new
   `FRAUD_CONTROLS` policy type), not in code.
3. **Model predictions** — `prediction` rows only, each with feature-snapshot references and time, tenant, subject,
   model name/version, evaluation and approval ids, score (only if calibrated), contributing features, threshold and
   policy version, and `decision_state`: `SHADOW` | `INSUFFICIENT_DATA` | `MODEL_DISABLED` | `SURFACED`. Shadow
   predictions are never shown to tenant users as findings.
4. **Human decisions** — `case_outcome` rows (immutable) on investigation cases.

There is no field anywhere meaning "fraud = true".

### Investigation cases

`anomaly_case` (tenant-scoped, number `CASE-YYYY-NNNNN`): title, subject, severity (max of its signals), status
`OPEN → IN_REVIEW → RESOLVED` (reopen allowed with reason), assignee (tenant member), linked signals (`case_signal`,
any source: risk signal, meter exception, tracking alert, SoD event, surfaced prediction), append-only notes
(`case_note`), and one outcome per resolution: `CONFIRMED_ISSUE` | `UNCONFIRMED` | `LEGITIMATE_EXPLANATION` with a
required explanation. Open signals for the same subject within the policy window are grouped into the open case
instead of opening new ones. Segregation of duties: the person a case is about (the supervisor whose capture, expense
or custody produced the evidence) cannot be assigned to it or resolve it. Wording in API and UI is neutral
("signal", "needs review", "explained"), never "fraud detected". Opening or escalating a case publishes the existing
`AnomalyDetected` notification seam.

### ML data foundation (Postgres, no separate feature platform — BL-020)

`feature_definition` (code, version, entity MACHINE/JOB/STAFF, domain spatial/meter/telemetry/finance/behavior,
window, description; immutable per version) and `feature_snapshot` (tenant, entity, feature code+version, `as_of`,
window, value, `data_cutoff`, computed_at). Point-in-time correctness: a snapshot `as_of` T uses only facts whose
event time **and** recording time are ≤ T. Training sets are generated per tenant only (cross-tenant pooling OFF by
default, §7), split temporally and grouped by machine, and described by a manifest (rows, time range, feature set
hash, split boundaries) stored with the MLflow run.

### Model lifecycle

MLflow (Compose service, Postgres backend store, MinIO artifacts) records runs, metrics and artifacts; the
application's own tables are the governance record: `model_version` (name, version, algorithm, MLflow run id,
feature set hash, training window, tenant scope, status `TRAINED → EVALUATED → APPROVED → DEPLOYED_SHADOW |
DEPLOYED_ACTIVE → RETIRED`, or `DISABLED`), `model_evaluation` (metrics against the statistical baseline, false
positive rate, calibration, data sufficiency, pass/fail against stated promotion criteria) and `model_approval`
(platform admin decision with reason; deploy, rollback and disable are explicit audited actions). A platform-wide hard
switch turns all inference off. R1 algorithms: robust z-score (median/MAD per machine) as the statistical baseline and
IsolationForest as the unsupervised candidate. Promotion beyond shadow requires passing evaluation and explicit
approval; until a tenant has enough representative history the status is `INSUFFICIENT_DATA` and the UI says why.

Inference runs in a bounded background worker. If MLflow, the model or the worker is unavailable, jobs, payments and
tracking continue unaffected, deterministic rules keep working, and predictions are simply absent with the reason
recorded. Drift (PSI per feature, training vs recent window) and inference latency are recorded per model version.

### Baseline insights

Fuel (litres per meter hour vs the machine's own history), utilization (meter/engine hours per available day) and
cash-flow trend (verified receipts less approved expenses per week), each returning `INSUFFICIENT_DATA` with the
minimum required history when it cannot be computed honestly.

## Consequences

- Gate 6 adds one module (`intelligence`), one policy type (`FRAUD_CONTROLS`), new tables with FORCE RLS, an MLflow
  Compose service and numeric dependencies (numpy, scikit-learn, MLflow client) in the backend image.
- Existing exception and alert reviews keep working; cases link to them rather than replacing them.
- Supervised fraud classification, predictive maintenance and pricing optimization remain backlog (BL-001..003).
- Gate 6D (as built): inference runs in the intelligence worker (hourly: refresh recent snapshots of tenants with a
  deployed model → score → daily drift) and after `asseta-ml snapshot`; one transaction and a 30 s budget per model,
  failures recorded in `inference_audit` and never raised. Two decision states were added to the four above:
  `BELOW_THRESHOLD` (an ACTIVE model scored below its threshold — kept for measurement, not shown) and
  `INSUFFICIENT_DATA` also covers an uncalibrated score under an ACTIVE model; `MODEL_DISABLED` is reserved because a
  disabled model never runs. Surfaced predictions join cases with the neutral title "Unusual machine-week pattern
  compared with this machine's history — needs review"; tenants can read only SURFACED rows (RLS).
- Drift compares the training split of the manifest with the most recent four weeks of snapshots after it
  (10 quantile bins + a missing bin, ≥ 30 rows per window); a new DRIFT level publishes `MlModelDriftDetected`
  (platform notification `ML_MODEL_DRIFT`).
- `feature_snapshot.source` (`observed` | `synthetic`) separates the development-only `asseta-ml demo` data; real
  training, inference of real models and insights read `observed` only, the demo model has its own name and a model
  trained on synthetic data can never be approved or activated.
- Insights reuse existing permissions (no new role-template grant): fuel/utilisation `tenant.fleet.read`, cash flow
  `tenant.finance.report`, the OCR override audit `tenant.meter.read`.
