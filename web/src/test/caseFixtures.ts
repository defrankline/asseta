import type {
  AnomalyCaseDetailDto,
  AnomalyCaseDto,
  CaseSignalDto,
  RiskSignalDto,
} from '../api/types';

export const CASE_ID = 'cccccccc-0000-4000-8000-000000000001';
export const MACHINE_ID = 'aaaaaaaa-0000-4000-8000-000000000001';
export const JOB_ID = 'bbbbbbbb-0000-4000-8000-000000000001';
export const EXPENSE_ID = 'eeeeeeee-0000-4000-8000-000000000001';
export const PERSON = {
  user_id: '4294e3e7-0000-4000-8000-000000000010',
  display_name: 'Rita Reviewer',
};

export function makeCase(overrides: Partial<AnomalyCaseDto> = {}): AnomalyCaseDto {
  return {
    id: CASE_ID,
    case_number: 'CASE-2026-00001',
    title: 'Engine activity without an active job',
    subject_type: 'MACHINE',
    subject_id: MACHINE_ID,
    machine_id: MACHINE_ID,
    job_id: null,
    staff_member_id: null,
    severity: 'WARNING',
    status: 'OPEN',
    assignee_user_id: null,
    assignee_name: null,
    opened_at: '2026-10-20T08:00:00Z',
    last_signal_at: '2026-10-20T07:30:00Z',
    resolved_at: null,
    resolved_by: null,
    signal_count: 1,
    latest_outcome: null,
    policy_version: 'FRAUD_CONTROLS:v1',
    version: 3,
    ...overrides,
  };
}

/** Evidence as stored by each backend rule (rules.py) — facts and thresholds only. */
export const RULE_EVIDENCE = {
  UNREPORTED_ENGINE_ACTIVITY: {
    basis: 'IGNITION',
    engine_on_from: '2026-10-20T05:00:00Z',
    engine_on_until: '2026-10-20T07:00:00Z',
    still_running_when_observed: false,
    uncovered_from: '2026-10-20T05:00:00Z',
    uncovered_until: '2026-10-20T06:30:00Z',
    uncovered_minutes: 90,
    capability_verified_since: '2026-09-01T00:00:00Z',
    running_jobs_nearby: [
      { job_id: JOB_ID, job_number: 'J-1001', from: '2026-10-20T06:30:00Z', to: null },
    ],
    threshold_minutes: 30,
  },
  DUPLICATE_RECEIPT: {
    receipt_sha256: 'abcdef0123456789abcdef',
    expense_id: EXPENSE_ID,
    incurred_at: '2026-10-19T10:00:00Z',
    amount: '45000.0000',
    currency: 'TZS',
    same_receipt_on: [
      {
        expense_id: 'eeeeeeee-0000-4000-8000-000000000002',
        incurred_at: '2026-10-18T09:00:00Z',
        submitted_at: '2026-10-18T09:05:00Z',
        amount: '45000.0000',
        currency: 'TZS',
      },
    ],
    lookback_days: 30,
  },
  FUEL_ALLOWANCE_EXCEEDED: {
    job_number: 'J-1002',
    opening_reading: '1200.0',
    closing_reading: '1210.0',
    meter_hours: '10.0',
    litres_into_machine: '300',
    litres_used: '250',
    litres_compared: '300',
    litres_per_meter_hour: '30.000',
    allowance_litres_per_meter_hour: '18',
    fuel_event_ids: [],
  },
  EXPENSE_THRESHOLD_EXCEEDED: {
    iso_week: '2026-W43',
    currency: 'TZS',
    approved_and_pending_total: '1250000.0000',
    threshold_per_week: '1000000',
    expense_ids: ['x1', 'x2', 'x3'],
  },
  CASH_NOT_HANDED_OVER: {
    currency: 'TZS',
    outstanding: '800000.0000',
    held_since: '2026-10-18T08:00:00Z',
    held_hours: 52.5,
    max_hours: 48,
    max_amount: '500000',
    limit: 'ABOVE_AMOUNT_LIMIT',
  },
  WORK_WITHOUT_AUTHORIZATION: {
    record_type: 'METER_CAPTURE',
    record_id: 'ffffffff-0000-4000-8000-000000000009',
    job_number: 'J-1003',
    occurred_at: '2026-10-20T04:00:00Z',
    received_at: '2026-10-20T09:00:00Z',
    job_status_now: 'IN_PROGRESS',
    job_approved_at: '2026-10-20T06:00:00Z',
    job_completed_at: null,
    tolerance_minutes: 15,
    recorder_supervisor_assigned: false,
    reasons: ['BEFORE_JOB_AUTHORIZED', 'SUPERVISOR_NOT_ASSIGNED_TO_MACHINE'],
  },
  UNEXPLAINED_ENGINE_HOURS: {
    machine_code: 'EXC-001',
    hours: '3.50',
    start_ref: 'eeeeeeee-0000-4000-8000-000000000001',
    end_ref: 'eeeeeeee-0000-4000-8000-000000000002',
    start_reading: '1000.00',
    end_reading: '1003.50',
    opened_at: '2026-10-16T09:00:00Z',
    age_days: 4,
    investigation_after_days: 3,
    classification: 'UNEXPLAINED',
  },
} as const;

export function makeCaseSignal(overrides: Partial<CaseSignalDto> = {}): CaseSignalDto {
  return {
    id: 'dddddddd-0000-4000-8000-000000000001',
    source_type: 'RISK_SIGNAL',
    source_id: '99999999-0000-4000-8000-000000000001',
    code: 'UNREPORTED_ENGINE_ACTIVITY',
    severity: 'WARNING',
    observed_at: '2026-10-20T05:00:00Z',
    evidence: { ...RULE_EVIDENCE.UNREPORTED_ENGINE_ACTIVITY },
    linked_at: '2026-10-20T08:00:00Z',
    ...overrides,
  };
}

export function makeDetail(overrides: Partial<AnomalyCaseDetailDto> = {}): AnomalyCaseDetailDto {
  return { case: makeCase(), signals: [makeCaseSignal()], notes: [], outcomes: [], ...overrides };
}

export function makeRiskSignal(overrides: Partial<RiskSignalDto> = {}): RiskSignalDto {
  return {
    id: '99999999-0000-4000-8000-000000000001',
    rule_code: 'UNREPORTED_ENGINE_ACTIVITY',
    rule_version: 1,
    severity: 'WARNING',
    subject_type: 'MACHINE',
    subject_id: MACHINE_ID,
    machine_id: MACHINE_ID,
    job_id: null,
    staff_member_id: null,
    window_start: '2026-10-20T05:00:00Z',
    window_end: '2026-10-20T06:30:00Z',
    evidence: { ...RULE_EVIDENCE.UNREPORTED_ENGINE_ACTIVITY },
    policy_version: 'FRAUD_CONTROLS:v1',
    dedupe_key: 'UEA:x',
    status: 'LINKED',
    created_at: '2026-10-20T07:00:00Z',
    ...overrides,
  };
}
