import type {
  CashFlowInsightDto,
  FuelEfficiencyInsightDto,
  ManualOverrideItemDto,
  ManualOverrideReportDto,
  MlModelVersionDetailDto,
  MlModelVersionDto,
  MlReadinessDto,
  MlSettingsDto,
  TenantInsightsDto,
  TenantMlStatusDto,
  TenantPredictionDto,
  UtilisationInsightDto,
} from '../api/types';
import { TENANT_A } from './fixtures';

export const MODEL_ID = 'abababab-0000-4000-8000-000000000001';
export const MACHINE_A = 'cdcdcdcd-0000-4000-8000-000000000001';
export const MACHINE_B = 'cdcdcdcd-0000-4000-8000-000000000002';
export const JOB_ID = 'efefefef-0000-4000-8000-000000000001';
export const CASE_ML = 'cacacaca-0000-4000-8000-000000000001';

export function makeReadiness(overrides: Partial<MlReadinessDto> = {}): MlReadinessDto {
  return {
    id: 'rdrdrdrd-0000-4000-8000-000000000001',
    tenant_id: TENANT_A,
    tenant_name: 'Acme Plant Hire',
    model_name: 'machine_week_anomaly',
    status: 'INSUFFICIENT_DATA',
    reasons: ['3 machines with usable history; at least 5 required.'],
    observed: { machines: 3, machine_weeks: 40, weeks_history: 6 },
    minimums: { min_machines: 5, min_machine_weeks: 80, min_weeks_history: 8 },
    snapshot_rows: 120,
    model_version_id: null,
    computed_at: '2026-10-20T08:00:00Z',
    ...overrides,
  };
}

export function makeTenantStatus(overrides: Partial<TenantMlStatusDto> = {}): TenantMlStatusDto {
  return {
    model_name: 'machine_week_anomaly',
    state: 'NOT_ENOUGH_HISTORY',
    label: 'Not enough history yet: 3 machines with usable history; at least 5 required.',
    readiness: makeReadiness(),
    deployed: null,
    inference_enabled: true,
    summary: 'Not enough history yet: 3 machines with usable history; at least 5 required.',
    ...overrides,
  };
}

export function makeFuel(
  overrides: Partial<FuelEfficiencyInsightDto> = {},
): FuelEfficiencyInsightDto {
  return {
    machine_id: MACHINE_A,
    asset_code: 'EX-01',
    machine_name: 'Excavator 1',
    status: 'READY',
    week_ending: '2026-10-18T21:00:00Z',
    current_litres_per_hour: 18.4,
    median_litres_per_hour: 12.1,
    band_low: 10.5,
    band_high: 13.8,
    outside_usual_range: true,
    weeks_observed: 8,
    min_weeks_required: 4,
    message: "Above this machine's usual range this week.",
    missing: [],
    ...overrides,
  };
}

export const FUEL_INSUFFICIENT = makeFuel({
  machine_id: MACHINE_B,
  asset_code: 'LD-02',
  machine_name: 'Loader 2',
  status: 'INSUFFICIENT_DATA',
  current_litres_per_hour: null,
  median_litres_per_hour: null,
  band_low: null,
  band_high: null,
  outside_usual_range: null,
  weeks_observed: 2,
  message: 'Not enough history.',
  missing: ['meter hours in 2 more weeks'],
});

export function makeUtilisation(
  overrides: Partial<UtilisationInsightDto> = {},
): UtilisationInsightDto {
  return {
    machine_id: MACHINE_A,
    asset_code: 'EX-01',
    machine_name: 'Excavator 1',
    status: 'READY',
    hours_per_available_day: 6.25,
    available_days: 84,
    weeks_observed: 12,
    min_weeks_required: 4,
    trend_hours_per_week: 1.5,
    trend: 'UP',
    weekly: [
      { week_ending: '2026-10-11T21:00:00Z', hours: 40, source: 'meter' },
      { week_ending: '2026-10-18T21:00:00Z', hours: 44, source: 'meter' },
    ],
    message: 'Hours per available day over the last 12 weeks.',
    missing: [],
    ...overrides,
  };
}

export function makeCashFlow(overrides: Partial<CashFlowInsightDto> = {}): CashFlowInsightDto {
  return {
    status: 'READY',
    currency: 'TZS',
    weeks: [
      {
        week_start: '2026-10-12T21:00:00Z',
        week_end: '2026-10-19T21:00:00Z',
        receipts: '1500000.0000',
        expenses: '400000.0000',
        net: '1100000.0000',
      },
    ],
    weeks_observed: 8,
    min_weeks_required: 6,
    trend_per_week: '25000.0000',
    trend: 'UP',
    median_weekly_net: '900000.0000',
    message: 'Weekly verified receipts less approved expenses.',
    missing: [],
    ...overrides,
  };
}

export function makeInsights(overrides: Partial<TenantInsightsDto> = {}): TenantInsightsDto {
  return {
    generated_at: '2026-10-22T08:00:00Z',
    history_weeks: 12,
    fuel_efficiency: [makeFuel(), FUEL_INSUFFICIENT],
    utilisation: [
      makeUtilisation(),
      makeUtilisation({
        machine_id: MACHINE_B,
        asset_code: 'LD-02',
        machine_name: 'Loader 2',
        status: 'INSUFFICIENT_DATA',
        hours_per_available_day: null,
        trend: null,
        trend_hours_per_week: null,
        weekly: [],
        weeks_observed: 1,
        missing: ['3 more observed weeks'],
      }),
    ],
    cash_flow: null,
    method: ["Fuel: litres per meter hour against the machine's own median."],
    ...overrides,
  };
}

export function makeOverride(
  overrides: Partial<ManualOverrideItemDto> = {},
): ManualOverrideItemDto {
  return {
    capture_id: 'c0c0c0c0-0000-4000-8000-000000000001',
    captured_at: '2026-10-20T07:30:00Z',
    received_at: '2026-10-20T07:31:00Z',
    machine_id: MACHINE_A,
    asset_code: 'EX-01',
    machine_name: 'Excavator 1',
    job_id: JOB_ID,
    job_number: 'JOB-2026-00042',
    kind: 'OPENING',
    capture_mode: 'OCR',
    manually_corrected: true,
    ocr_value: '1234.5',
    entered_value: '1243.5',
    difference: '9.0',
    ocr_confidence: 0.82,
    ocr_engine: 'tesseract',
    captured_by_user_id: null,
    captured_by_name: 'Sam Supervisor',
    state: 'ACCEPTED',
    exception_id: null,
    exception_status: null,
    ...overrides,
  };
}

export function makeOverrideReport(items = [makeOverride()]): ManualOverrideReportDto {
  return {
    summary: {
      total: items.length,
      manual_corrections: 1,
      manual_mode_with_ocr: 0,
      value_differs: 1,
      exceptions_open: 0,
    },
    items,
    total: items.length,
    page: 1,
    page_size: 25,
  };
}

export function makeObservation(overrides: Partial<TenantPredictionDto> = {}): TenantPredictionDto {
  return {
    id: 'p0p0p0p0-0000-4000-8000-000000000001',
    machine_id: MACHINE_A,
    week_ending: '2026-10-18T21:00:00Z',
    model_name: 'machine_week_anomaly',
    model_version: 3,
    observations: ['Fuel per meter hour well above this machine’s usual weeks.'],
    case_id: CASE_ML,
    created_at: '2026-10-19T02:00:00Z',
    ...overrides,
  };
}

export function makeModel(overrides: Partial<MlModelVersionDto> = {}): MlModelVersionDto {
  return {
    id: MODEL_ID,
    tenant_id: TENANT_A,
    tenant_name: 'Acme Plant Hire',
    name: 'machine_week_anomaly',
    version: 3,
    algorithm: 'ISOLATION_FOREST',
    baseline_algorithm: 'ROBUST_Z_BASELINE',
    feature_set_hash: 'f'.repeat(64),
    training_window_start: '2026-04-01T00:00:00Z',
    training_window_end: '2026-09-30T00:00:00Z',
    mlflow_run_id: 'run-123',
    tracking_note: null,
    artifact_sha256: 'a'.repeat(64),
    status: 'EVALUATED',
    status_changed_at: '2026-10-01T00:00:00Z',
    deployed_at: null,
    evaluation_passed: true,
    created_at: '2026-10-01T00:00:00Z',
    lock_version: 4,
    ...overrides,
  };
}

export function makeModelDetail(
  model: Partial<MlModelVersionDto> = {},
  overrides: Partial<MlModelVersionDetailDto> = {},
): MlModelVersionDetailDto {
  return {
    model: makeModel(model),
    evaluation: {
      id: 'e0e0e0e0-0000-4000-8000-000000000001',
      model_version_id: MODEL_ID,
      metrics: {
        baseline: { recall_at_k: 0.4, alert_rate: 0.03, calibrated: 1 },
        candidate: { recall_at_k: 0.62, alert_rate: 0.02, calibrated: 1 },
        recall_lift: 0.22,
      },
      readiness: { status: 'READY' },
      criteria: { promotion: { min_recall_lift: 0.05 }, sufficiency: { min_machines: 5 } },
      passed: true,
      reasons: ['Recall lift 0.22 meets the 0.05 minimum.'],
      evaluated_at: '2026-10-01T00:00:00Z',
    },
    approvals: [
      {
        id: 'a0a0a0a0-0000-4000-8000-000000000001',
        model_version_id: MODEL_ID,
        action: 'TRAIN',
        from_status: null,
        to_status: 'EVALUATED',
        related_model_version_id: null,
        reason: 'Training run summary',
        decided_by: null,
        decided_by_name: null,
        decided_at: '2026-10-01T00:00:00Z',
      },
    ],
    manifest: {
      rows: { train: 300, validation: 60, test: 60 },
      entities: 9,
      feature_codes: ['fuel_per_meter_hour', 'engine_hours'],
      train_end: '2026-08-31',
      validation_end: '2026-09-15',
      purged_rows: 4,
      content_hash: 'c'.repeat(64),
    },
    drift: {
      id: 'd0d0d0d0-0000-4000-8000-000000000001',
      model_version_id: MODEL_ID,
      computed_at: '2026-10-21T03:00:00Z',
      train_start: '2026-04-01T00:00:00Z',
      train_end: '2026-08-31T00:00:00Z',
      recent_start: '2026-09-23T00:00:00Z',
      recent_end: '2026-10-21T00:00:00Z',
      n_train: 300,
      n_recent: 40,
      features: [
        {
          feature: 'fuel_per_meter_hour',
          psi: 0.31,
          level: 'DRIFT',
          n_expected: 300,
          n_actual: 40,
        },
        { feature: 'engine_hours', psi: 0.04, level: 'STABLE', n_expected: 300, n_actual: 40 },
      ],
      level: 'DRIFT',
      summary: '1 of 2 features drifted.',
    },
    monitoring: {
      latency_p50_ms: 120,
      latency_p95_ms: 480,
      runs_by_outcome: { OK: 10, ERROR: 1 },
      predictions_by_state: { SHADOW: 90 },
      last_inference_at: '2026-10-21T04:00:00Z',
      last_error: 'MLflow unavailable',
    },
    ...overrides,
  };
}

export const SETTINGS_ON: MlSettingsDto = {
  inference_enabled: true,
  reason: 'Platform default: inference may run for deployed models only.',
  updated_by: null,
  updated_at: null,
  lock_version: 0,
};
