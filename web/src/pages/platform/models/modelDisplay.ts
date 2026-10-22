import type { MlLifecycleAction } from '../../../api/services/platformMlService';
import type {
  DecisionState,
  MlPredictionDto,
  DriftSummaryLevel,
  InferenceOutcome,
  MlEvaluationDto,
  ModelAction,
  ModelAlgorithm,
  ModelStatus,
  ReadinessState,
} from '../../../api/types';
import type { SelectOption } from '../../../components/forms/FormikSelectField';
import type { StatusTone } from '../../../components/display/StatusChip';

/**
 * Labels and the lifecycle graph for governed model versions (backend `ml_lifecycle._ACTION_FROM`,
 * `MODEL_TRANSITIONS`). Scores are model-specific and only a calibrated percentile is ever shown
 * as one; nothing here is presented as a probability.
 */

export const MODEL_STATUS_LABELS: Readonly<Record<ModelStatus, string>> = {
  TRAINED: 'Trained',
  EVALUATED: 'Evaluated',
  APPROVED: 'Approved',
  DEPLOYED_SHADOW: 'Deployed (shadow)',
  DEPLOYED_ACTIVE: 'Deployed (active)',
  RETIRED: 'Retired',
  DISABLED: 'Disabled',
  REJECTED: 'Rejected',
};

export const MODEL_STATUS_TONES: Readonly<Record<ModelStatus, StatusTone>> = {
  TRAINED: 'default',
  EVALUATED: 'info',
  APPROVED: 'info',
  DEPLOYED_SHADOW: 'warning',
  DEPLOYED_ACTIVE: 'success',
  RETIRED: 'default',
  DISABLED: 'error',
  REJECTED: 'default',
};

export const MODEL_STATUS_OPTIONS: readonly SelectOption[] = (
  Object.keys(MODEL_STATUS_LABELS) as ModelStatus[]
).map((s) => ({ value: s, label: MODEL_STATUS_LABELS[s] }));

export const ALGORITHM_LABELS: Readonly<Record<ModelAlgorithm, string>> = {
  ISOLATION_FOREST: 'Isolation forest',
  ROBUST_Z_BASELINE: 'Robust z-score (baseline)',
};

export const ACTION_LABELS: Readonly<Record<ModelAction, string>> = {
  TRAIN: 'Trained',
  APPROVE: 'Approve',
  REJECT: 'Reject',
  DEPLOY_SHADOW: 'Deploy in shadow',
  DEPLOY_ACTIVE: 'Deploy active',
  ROLLBACK: 'Roll back',
  DISABLE: 'Disable',
  RETIRE: 'Retire',
};

export const READINESS_LABELS: Readonly<Record<ReadinessState, string>> = {
  READY: 'Ready',
  INSUFFICIENT_DATA: 'Not enough history',
};

export const READINESS_TONES: Readonly<Record<ReadinessState, StatusTone>> = {
  READY: 'success',
  INSUFFICIENT_DATA: 'warning',
};

export const READINESS_OPTIONS: readonly SelectOption[] = [
  { value: 'READY', label: READINESS_LABELS.READY },
  { value: 'INSUFFICIENT_DATA', label: READINESS_LABELS.INSUFFICIENT_DATA },
];

export const DRIFT_TONES: Readonly<Record<string, StatusTone>> = {
  STABLE: 'success',
  WATCH: 'warning',
  DRIFT: 'error',
  INSUFFICIENT_DATA: 'default',
} satisfies Readonly<Record<DriftSummaryLevel, StatusTone>>;

export const DRIFT_LABELS: Readonly<Record<string, string>> = {
  STABLE: 'Stable',
  WATCH: 'Watch',
  DRIFT: 'Drift',
  INSUFFICIENT_DATA: 'Not enough data',
} satisfies Readonly<Record<DriftSummaryLevel, string>>;

export const DECISION_LABELS: Readonly<Record<DecisionState, string>> = {
  SHADOW: 'Shadow (not shown)',
  SURFACED: 'Surfaced for review',
  BELOW_THRESHOLD: 'Below threshold',
  INSUFFICIENT_DATA: 'Not enough data',
  MODEL_DISABLED: 'Model disabled',
};

export const DECISION_TONES: Readonly<Record<DecisionState, StatusTone>> = {
  SHADOW: 'default',
  SURFACED: 'warning',
  BELOW_THRESHOLD: 'default',
  INSUFFICIENT_DATA: 'default',
  MODEL_DISABLED: 'default',
};

export const DECISION_OPTIONS: readonly SelectOption[] = (
  Object.keys(DECISION_LABELS) as DecisionState[]
).map((s) => ({ value: s, label: DECISION_LABELS[s] }));

export const OUTCOME_TONES: Readonly<Record<InferenceOutcome, StatusTone>> = {
  OK: 'success',
  SKIPPED: 'default',
  ERROR: 'error',
};

export const OUTCOME_OPTIONS: readonly SelectOption[] = [
  { value: 'OK', label: 'OK' },
  { value: 'SKIPPED', label: 'Skipped' },
  { value: 'ERROR', label: 'Error' },
];

const DEPLOYED: ReadonlySet<ModelStatus> = new Set(['DEPLOYED_SHADOW', 'DEPLOYED_ACTIVE']);

/** From-statuses per action (backend `_ACTION_FROM`); ROLLBACK applies to the deployed version. */
const ACTION_FROM: Readonly<Record<MlLifecycleAction, ReadonlySet<ModelStatus>>> = {
  APPROVE: new Set(['EVALUATED', 'DEPLOYED_SHADOW']),
  REJECT: new Set(['TRAINED', 'EVALUATED', 'APPROVED']),
  DEPLOY_SHADOW: new Set(['EVALUATED', 'APPROVED']),
  DEPLOY_ACTIVE: new Set(['EVALUATED', 'APPROVED', 'DEPLOYED_SHADOW']),
  ROLLBACK: DEPLOYED,
  DISABLE: new Set([
    'TRAINED',
    'EVALUATED',
    'APPROVED',
    'DEPLOYED_SHADOW',
    'DEPLOYED_ACTIVE',
    'RETIRED',
  ]),
  RETIRE: new Set(['EVALUATED', 'APPROVED', 'DEPLOYED_SHADOW', 'DEPLOYED_ACTIVE']),
};

/** Display order of the lifecycle buttons. */
const ACTION_ORDER: readonly MlLifecycleAction[] = [
  'APPROVE',
  'DEPLOY_SHADOW',
  'DEPLOY_ACTIVE',
  'ROLLBACK',
  'REJECT',
  'RETIRE',
  'DISABLE',
];

/** Actions the lifecycle graph allows from `status` (the server still checks preconditions). */
export function allowedActions(status: ModelStatus): MlLifecycleAction[] {
  return ACTION_ORDER.filter((a) => ACTION_FROM[a].has(status));
}

export const DESTRUCTIVE_ACTIONS: ReadonlySet<MlLifecycleAction> = new Set([
  'REJECT',
  'RETIRE',
  'DISABLE',
  'ROLLBACK',
]);

/**
 * Why Approve is unavailable, or null when the evaluation passed. The server refuses approval
 * without a passing evaluation (EVALUATION_REQUIRED / EVALUATION_NOT_PASSED); say so up front.
 */
export function approvalBlockedReason(evaluation: MlEvaluationDto | null): string | null {
  if (evaluation === null) return 'No evaluation recorded yet: run training to evaluate it.';
  if (evaluation.passed) return null;
  const reasons = evaluation.reasons.map((r) => r.trim()).filter((r) => r !== '');
  return reasons.length > 0
    ? `Evaluation did not pass: ${reasons.join(' ')}`
    : 'Evaluation did not pass.';
}

/** What each action does, in plain words (shown in its confirmation dialog). */
export const ACTION_EFFECTS: Readonly<Record<MlLifecycleAction, string>> = {
  APPROVE:
    'Records your approval of this version. It needs a passing evaluation; active deployment is a separate step.',
  REJECT: 'Closes this candidate. It can no longer be deployed.',
  DEPLOY_SHADOW:
    'Runs this version in shadow mode: predictions are recorded for the platform and never shown to the tenant. Any other deployed version of this model is retired.',
  DEPLOY_ACTIVE:
    'Makes this version active: predictions at or above the threshold open cases for human review. Any other deployed version of this model is retired.',
  ROLLBACK:
    'Retires this version and redeploys the previously deployed version in the mode it had.',
  DISABLE: 'Stops this version immediately and for good. Deterministic rules keep working.',
  RETIRE: 'Takes this version out of service. Deterministic rules keep working.',
};

/** Stable server error codes → what the operator can do. */
export const MODEL_ERROR_HINTS: Readonly<Record<string, string>> = {
  EVALUATION_NOT_PASSED:
    'The evaluation did not meet the promotion criteria. Deploy in shadow to keep observing it, or train a new version.',
  EVALUATION_REQUIRED: 'Wait for the evaluation to be recorded (run training), then try again.',
  APPROVAL_REQUIRED: 'Approve this version first, then deploy it as active.',
  SYNTHETIC_MODEL:
    'This version was trained on synthetic demo data. It can only run in shadow; train on observed data to promote.',
  ALREADY_APPROVED: 'This version is already approved; reload to see its current state.',
  INVALID_MODEL_TRANSITION: 'The model changed state; reload to see the actions now allowed.',
  MODEL_NOT_DEPLOYED: 'Only the deployed version can be rolled back.',
  NO_PREVIOUS_DEPLOYMENT:
    'There is no earlier deployed version to return to; retire or disable instead.',
  MODEL_ALREADY_DEPLOYED: 'Another version was deployed meanwhile; reload and try again.',
};

/** `0.123` → `0.123`; NaN/absent → `—`. Metrics are model-specific, never probabilities. */
export function metricText(value: unknown): string {
  if (typeof value === 'number')
    return Number.isFinite(value)
      ? value.toLocaleString('en-US', { maximumFractionDigits: 3 })
      : '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (value === null || value === undefined) return '—';
  return typeof value === 'string' ? value : JSON.stringify(value);
}

export const shortHash = (value: string | null | undefined): string =>
  value === null || value === undefined || value === '' ? '—' : `${value.slice(0, 12)}…`;

/** 0.25 -> "25th", 0.983 -> "98.3rd": a calibrated score is a fraction of held-out weeks scoring lower. */
export function ordinalPercentile(fraction: number | string | null): string {
  const n = Number(fraction);
  if (fraction === null || !Number.isFinite(n)) return '—';
  const pct = Math.round(n * 1000) / 10;
  const whole = Math.trunc(pct);
  const suffix =
    whole % 100 >= 11 && whole % 100 <= 13
      ? 'th'
      : (({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[whole % 10] ?? 'th');
  return `${String(pct)}${suffix}`;
}

/** A score is a calibrated percentile only when calibrated; otherwise a raw, model-specific value. */
export function scoreText(p: MlPredictionDto): string {
  if (p.calibrated && p.score !== null) {
    return `${ordinalPercentile(p.score)} percentile (threshold ${ordinalPercentile(p.threshold)})`;
  }
  return p.raw_score === null ? '—' : `Uncalibrated raw ${metricText(p.raw_score)}`;
}
