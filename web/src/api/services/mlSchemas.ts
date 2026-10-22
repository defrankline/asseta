import { array, mixed, object, type Schema } from 'yup';
import type {
  CashFlowInsightDto,
  CashFlowWeekDto,
  DecisionState,
  DriftSummaryLevel,
  FuelEfficiencyInsightDto,
  InferenceOutcome,
  InsightStatus,
  InsightTrend,
  ManualOverrideItemDto,
  ManualOverrideReportDto,
  MlApprovalDto,
  MlDriftDto,
  MlDriftFeatureDto,
  MlEvaluationDto,
  MlInferenceAuditDto,
  MlModelVersionDetailDto,
  MlModelVersionDto,
  MlPredictionDto,
  MlReadinessDto,
  MlSettingsDto,
  MlSnapshotRunDto,
  MlTrainingRunDto,
  ModelAction,
  ModelAlgorithm,
  ModelStatus,
  ReadinessState,
  TenantInsightsDto,
  TenantMlState,
  TenantMlStatusDto,
  TenantPredictionDto,
  UtilisationInsightDto,
  WeeklyHoursDto,
} from '../types';
import {
  bool,
  id,
  idList,
  int,
  nullableBool,
  nullableId,
  nullableInt,
  nullableNum,
  nullableOneOf,
  nullableText,
  num,
  oneOf,
  record,
  text,
} from './schemaKit';

// ---- Governed ML (ADR-007): model versions, lifecycle log, monitoring ----

export const MODEL_STATUSES: readonly ModelStatus[] = [
  'TRAINED',
  'EVALUATED',
  'APPROVED',
  'DEPLOYED_SHADOW',
  'DEPLOYED_ACTIVE',
  'RETIRED',
  'DISABLED',
  'REJECTED',
];
export const MODEL_ACTIONS: readonly ModelAction[] = [
  'TRAIN',
  'APPROVE',
  'REJECT',
  'DEPLOY_SHADOW',
  'DEPLOY_ACTIVE',
  'ROLLBACK',
  'DISABLE',
  'RETIRE',
];
export const MODEL_ALGORITHMS: readonly ModelAlgorithm[] = [
  'ISOLATION_FOREST',
  'ROBUST_Z_BASELINE',
];
export const READINESS_STATES: readonly ReadinessState[] = ['READY', 'INSUFFICIENT_DATA'];
export const DECISION_STATES: readonly DecisionState[] = [
  'SHADOW',
  'SURFACED',
  'BELOW_THRESHOLD',
  'INSUFFICIENT_DATA',
  'MODEL_DISABLED',
];
export const DRIFT_LEVELS: readonly DriftSummaryLevel[] = [
  'STABLE',
  'WATCH',
  'DRIFT',
  'INSUFFICIENT_DATA',
];
export const INFERENCE_OUTCOMES: readonly InferenceOutcome[] = ['OK', 'SKIPPED', 'ERROR'];
export const TENANT_ML_STATES: readonly TenantMlState[] = [
  'MODEL_OFF',
  'NOT_ASSESSED',
  'NOT_ENOUGH_HISTORY',
  'EVALUATING',
  'LEARNING_SHADOW',
  'ACTIVE',
];
const INSIGHT_STATUSES: readonly InsightStatus[] = ['READY', 'INSUFFICIENT_DATA'];
const TRENDS: readonly InsightTrend[] = ['UP', 'DOWN', 'FLAT'];

function isNumberRecord(value: unknown): value is Record<string, number> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    Object.values(value).every((v) => typeof v === 'number')
  );
}

/** JSON object of counts (rows per split, runs per outcome). */
const countRecord = () => mixed<Record<string, number>>(isNumberRecord).required();

const modelFields = {
  id: id(),
  tenant_id: id(),
  tenant_name: nullableText().default(null),
  name: text(),
  version: int(),
  algorithm: oneOf(MODEL_ALGORITHMS),
  baseline_algorithm: oneOf(MODEL_ALGORITHMS),
  feature_set_hash: text(),
  training_window_start: nullableText(),
  training_window_end: nullableText(),
  mlflow_run_id: nullableText(),
  tracking_note: nullableText(),
  artifact_sha256: text(),
  status: oneOf(MODEL_STATUSES),
  status_changed_at: text(),
  deployed_at: nullableText(),
  evaluation_passed: nullableBool().default(null),
  created_at: text(),
  lock_version: int(),
};

export const mlModelVersionSchema: Schema<MlModelVersionDto> = object(modelFields);

export const mlApprovalSchema: Schema<MlApprovalDto> = object({
  id: id(),
  model_version_id: id(),
  action: oneOf(MODEL_ACTIONS),
  from_status: nullableOneOf(MODEL_STATUSES),
  to_status: oneOf(MODEL_STATUSES),
  related_model_version_id: nullableId(),
  reason: text(),
  decided_by: nullableId(),
  decided_by_name: nullableText().default(null),
  decided_at: text(),
});

const manifestFields = {
  rows: countRecord(),
  entities: int(),
  feature_codes: array(text()).required(),
  train_end: nullableText(),
  validation_end: nullableText(),
  purged_rows: nullableInt(),
  content_hash: nullableText(),
};

const driftFeatureSchema: Schema<MlDriftFeatureDto> = object({
  feature: text(),
  psi: nullableNum(),
  level: text(),
  n_expected: int(),
  n_actual: int(),
});

const driftFields = {
  id: id(),
  model_version_id: id(),
  computed_at: text(),
  train_start: nullableText(),
  train_end: nullableText(),
  recent_start: nullableText(),
  recent_end: nullableText(),
  n_train: int(),
  n_recent: int(),
  features: array(driftFeatureSchema).required(),
  level: oneOf(DRIFT_LEVELS),
  summary: text(),
};

export const mlDriftSchema: Schema<MlDriftDto> = object(driftFields);

const monitoringFields = {
  latency_p50_ms: nullableNum(),
  latency_p95_ms: nullableNum(),
  runs_by_outcome: countRecord(),
  predictions_by_state: countRecord(),
  last_inference_at: nullableText(),
  last_error: nullableText(),
};

const evaluationFields = {
  id: id(),
  model_version_id: id(),
  metrics: record(),
  readiness: record(),
  criteria: record(),
  passed: bool(),
  reasons: array(text()).required(),
  evaluated_at: text(),
};

export const mlEvaluationSchema: Schema<MlEvaluationDto> = object(evaluationFields);

export const mlModelDetailSchema: Schema<MlModelVersionDetailDto> = object({
  model: object(modelFields).required(),
  evaluation: object(evaluationFields).nullable().defined(),
  approvals: array(mlApprovalSchema).required(),
  manifest: object(manifestFields).required(),
  drift: object(driftFields).nullable().default(null),
  monitoring: object(monitoringFields).nullable().default(null),
});

export const mlPredictionSchema: Schema<MlPredictionDto> = object({
  id: id(),
  tenant_id: id(),
  model_version_id: id(),
  model_name: text(),
  model_version_number: int(),
  deployment_mode: text(),
  evaluation_id: nullableId(),
  approval_id: nullableId(),
  subject_type: text(),
  subject_id: id(),
  as_of: text(),
  feature_set_hash: text(),
  feature_snapshot_ids: idList(),
  data_cutoff: nullableText(),
  features_present: int(),
  score: nullableText(),
  raw_score: nullableNum(),
  calibrated: bool(),
  baseline_score: nullableText(),
  baseline_raw_score: nullableNum(),
  threshold: text(),
  would_surface: bool(),
  contributions: array(record()).required(),
  explanations: array(text()).required(),
  policy_version: text(),
  decision_state: oneOf(DECISION_STATES),
  case_id: nullableId(),
  inference_run_id: id(),
  created_at: text(),
});

export const mlInferenceAuditSchema: Schema<MlInferenceAuditDto> = object({
  id: id(),
  tenant_id: nullableId(),
  model_version_id: nullableId(),
  inference_run_id: id(),
  started_at: text(),
  latency_ms: int(),
  input_rows: int(),
  predictions_written: int(),
  surfaced: int(),
  outcome: oneOf(INFERENCE_OUTCOMES),
  reason: nullableText(),
});

export const mlSettingsSchema: Schema<MlSettingsDto> = object({
  inference_enabled: bool(),
  reason: text(),
  updated_by: nullableId(),
  updated_at: nullableText(),
  lock_version: int(),
});

const readinessFields = {
  id: id(),
  tenant_id: id(),
  tenant_name: nullableText().default(null),
  model_name: text(),
  status: oneOf(READINESS_STATES),
  reasons: array(text()).required(),
  observed: record(),
  minimums: record(),
  snapshot_rows: int(),
  model_version_id: nullableId(),
  computed_at: text(),
};

export const mlReadinessSchema: Schema<MlReadinessDto> = object(readinessFields);

export const mlSnapshotRunSchema: Schema<MlSnapshotRunDto> = object({
  run_id: id(),
  tenant_id: id(),
  week_ends: array(text()).required(),
  machines: int(),
  written: int(),
  skipped_existing: int(),
  skipped_future: int(),
});

export const mlTrainingRunSchema: Schema<MlTrainingRunDto> = object({
  readiness: object(readinessFields).required(),
  model: object(modelFields).nullable().defined(),
});

// ---- Tenant-facing: plain status and surfaced observations (never a score) ----

export const tenantMlStatusSchema: Schema<TenantMlStatusDto> = object({
  model_name: text(),
  state: oneOf(TENANT_ML_STATES),
  label: text(),
  readiness: object(readinessFields).nullable().defined(),
  deployed: object({
    name: text(),
    version: int(),
    mode: text(),
    deployed_at: nullableText(),
  })
    .nullable()
    .defined(),
  inference_enabled: bool(),
  summary: text(),
});

export const tenantPredictionSchema: Schema<TenantPredictionDto> = object({
  id: id(),
  machine_id: id(),
  week_ending: text(),
  model_name: text(),
  model_version: int(),
  observations: array(text()).required(),
  case_id: nullableId(),
  created_at: text(),
});

// ---- Baseline insights and the OCR manual-override audit ----

const fuelSchema: Schema<FuelEfficiencyInsightDto> = object({
  machine_id: id(),
  asset_code: text(),
  machine_name: text(),
  status: oneOf(INSIGHT_STATUSES),
  week_ending: nullableText(),
  current_litres_per_hour: nullableNum(),
  median_litres_per_hour: nullableNum(),
  band_low: nullableNum(),
  band_high: nullableNum(),
  outside_usual_range: nullableBool(),
  weeks_observed: int(),
  min_weeks_required: int(),
  message: text(),
  missing: array(text()).required(),
});

const weeklyHoursSchema: Schema<WeeklyHoursDto> = object({
  week_ending: text(),
  hours: num(),
  source: oneOf(['meter', 'engine', 'none'] as const),
});

const utilisationSchema: Schema<UtilisationInsightDto> = object({
  machine_id: id(),
  asset_code: text(),
  machine_name: text(),
  status: oneOf(INSIGHT_STATUSES),
  hours_per_available_day: nullableNum(),
  available_days: int(),
  weeks_observed: int(),
  min_weeks_required: int(),
  trend_hours_per_week: nullableNum(),
  trend: nullableOneOf(TRENDS),
  weekly: array(weeklyHoursSchema).required(),
  message: text(),
  missing: array(text()).required(),
});

const cashFlowWeekSchema: Schema<CashFlowWeekDto> = object({
  week_start: text(),
  week_end: text(),
  receipts: text(),
  expenses: text(),
  net: text(),
});

const cashFlowFields = {
  status: oneOf(INSIGHT_STATUSES),
  currency: text(),
  weeks: array(cashFlowWeekSchema).required(),
  weeks_observed: int(),
  min_weeks_required: int(),
  trend_per_week: nullableText(),
  trend: nullableOneOf(TRENDS),
  median_weekly_net: nullableText(),
  message: text(),
  missing: array(text()).required(),
};

export const cashFlowInsightSchema: Schema<CashFlowInsightDto> = object(cashFlowFields);

export const tenantInsightsSchema: Schema<TenantInsightsDto> = object({
  generated_at: text(),
  history_weeks: int(),
  fuel_efficiency: array(fuelSchema).required(),
  utilisation: array(utilisationSchema).required(),
  cash_flow: object(cashFlowFields).nullable().defined(),
  method: array(text()).required(),
});

const overrideItemSchema: Schema<ManualOverrideItemDto> = object({
  capture_id: id(),
  captured_at: text(),
  received_at: text(),
  machine_id: id(),
  asset_code: text(),
  machine_name: text(),
  job_id: id(),
  job_number: nullableText(),
  kind: text(),
  capture_mode: text(),
  manually_corrected: bool(),
  ocr_value: nullableText(),
  entered_value: text(),
  difference: nullableText(),
  ocr_confidence: nullableNum(),
  ocr_engine: nullableText(),
  captured_by_user_id: nullableId(),
  captured_by_name: nullableText(),
  state: text(),
  exception_id: nullableId(),
  exception_status: nullableText(),
});

export const manualOverrideReportSchema: Schema<ManualOverrideReportDto> = object({
  summary: object({
    total: int(),
    manual_corrections: int(),
    manual_mode_with_ocr: int(),
    value_differs: int(),
    exceptions_open: int(),
  }).required(),
  items: array(overrideItemSchema).required(),
  total: int(),
  page: int(),
  page_size: int(),
});
