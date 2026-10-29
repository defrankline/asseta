import type {
  AcknowledgementDto,
  ContractDto,
  ExceptionDto,
  JobDto,
  JobSummaryDto,
  MachineDto,
  MeterCaptureDto,
  ResetDto,
} from '../api/types';

export const JOB_ID = 'dddddddd-0000-4000-8000-000000000001';
export const MACHINE_ID = 'aaaaaaaa-0000-4000-8000-000000000001';

export function makeJob(overrides: Partial<JobDto> = {}): JobDto {
  return {
    id: JOB_ID,
    contract_id: 'cccccccc-0000-4000-8000-000000000001',
    job_number: 'J-100',
    machine_id: MACHINE_ID,
    job_site_id: null,
    supervisor_id: null,
    status: 'DRAFT',
    planned_start: '2026-10-21T06:00:00Z',
    planned_end: null,
    currency: 'TZS',
    hourly_rate: '150000.0000',
    minimum_hours: '8.00',
    standby_treatment: 'EXCLUDED',
    standby_rate: null,
    mobilization_fee: '0.0000',
    discount_percent: '0.00',
    tax_rate_percent: '18.00',
    rate_source: 'NEGOTIATED',
    billing_mode: 'INVOICE',
    approved_at: null,
    started_at: null,
    completed_at: null,
    version: 1,
    ...overrides,
  };
}

export function makeSummary(overrides: Partial<JobSummaryDto> = {}): JobSummaryDto {
  return {
    job: makeJob({ status: 'COMPLETED' }),
    opening_reading: '1200.4',
    closing_reading: '1208.8',
    meter_hours: '8.4',
    nonbillable_hours: '1.50',
    billable_hours: '8.0',
    standby_hours: '0.00',
    open_exceptions: 1,
    blocking_exceptions: 1,
    billing_ready: false,
    policy_version: 'HB:P1',
    ...overrides,
  };
}

export const CONTRACT: ContractDto = {
  id: 'cccccccc-0000-4000-8000-000000000001',
  customer_id: 'eeeeeeee-0000-4000-8000-000000000001',
  contract_number: 'C-1',
  job_site_id: null,
  currency: 'TZS',
  status: 'ACTIVE',
  starts_on: '2026-10-01T00:00:00Z',
  ends_on: null,
  reference: null,
  version: 1,
};

export const MACHINE: MachineDto = {
  id: MACHINE_ID,
  asset_code: 'EX-01',
  name: 'Excavator',
  category_id: null,
  operating_area_id: null,
  manufacturer: null,
  model: null,
  serial_number: null,
  year_of_manufacture: null,
  capacity_value: null,
  capacity_unit: null,
  meter_decimal_places: 1,
  ownership: 'OWNED',
  status: 'ACTIVE',
  version: 1,
  created_at: '2026-10-01T00:00:00Z',
  billing_enrolled: false,
  primary_tracker_id: null,
  primary_tracker_label: null,
};

export function makeCapture(overrides: Partial<MeterCaptureDto> = {}): MeterCaptureDto {
  return {
    id: 'ffffffff-0000-4000-8000-000000000001',
    job_id: JOB_ID,
    machine_id: MACHINE_ID,
    kind: 'OPENING',
    capture_mode: 'AUTOMATIC',
    reading: '1200.4',
    ocr_value: '1200.4',
    ocr_confidence: 0.93,
    manually_corrected: false,
    photo_attachment_id: '88888888-0000-4000-8000-000000000001',
    photo_sha256: 'ab'.repeat(32),
    gps_status: 'FIX',
    latitude: -6.8,
    longitude: 39.28,
    accuracy_m: 12,
    location_captured_at: '2026-10-21T06:00:00Z',
    captured_at: '2026-10-21T06:00:05Z',
    received_at: '2026-10-21T06:00:09Z',
    policy_version: 'MC:P1+T2',
    state: 'ACCEPTED',
    tracker_comparison: {
      compared: true,
      distance_m: 412.3,
      allowed_m: 162,
      tracker_time: '2026-10-21T05:59:50Z',
      time_offset_s: 10,
      tracker_latitude: -6.8037,
      tracker_longitude: 39.2812,
      tracker_accuracy_m: 8,
    },
    supersedes_id: null,
    ...overrides,
  };
}

export function makeException(overrides: Partial<ExceptionDto> = {}): ExceptionDto {
  return {
    id: '99999999-0000-4000-8000-000000000001',
    job_id: JOB_ID,
    machine_id: MACHINE_ID,
    meter_capture_id: 'ffffffff-0000-4000-8000-000000000001',
    exception_type: 'LOCATION_MISMATCH',
    severity: 'CRITICAL',
    blocking: true,
    evidence: {
      compared: true,
      distance_m: 412.3,
      allowed_m: 162,
      tracker_time: '2026-10-21T05:59:50Z',
      time_offset_s: 10,
    },
    policy_version: 'MC:P1+T2',
    status: 'OPEN',
    review_note: null,
    reviewed_at: null,
    created_at: '2026-10-21T06:00:09Z',
    ...overrides,
  };
}

/** The signed-in fixture user (`makeMe().user_id`). */
export const ME_ID = '33333333-3333-4333-8333-333333333333';

export function makeReset(overrides: Partial<ResetDto> = {}): ResetDto {
  return {
    id: '77777777-0000-4000-8000-000000000001',
    machine_id: MACHINE_ID,
    old_reading: '9999.9',
    new_reading: '0.0',
    effective_at: '2026-10-21T08:00:00Z',
    reason: 'Hour meter replaced after failure',
    evidence_attachment_id: null,
    status: 'PENDING',
    requested_by: '44444444-4444-4444-8444-444444444444',
    decided_at: null,
    ...overrides,
  };
}

export function makeAck(overrides: Partial<AcknowledgementDto> = {}): AcknowledgementDto {
  return {
    id: '66666666-0000-4000-8000-000000000001',
    method: 'SIGNATURE',
    signer_name: 'Asha Mwita',
    signer_phone: '+255700000001',
    signature_attachment_id: '55555555-0000-4000-8000-000000000001',
    acknowledged_hours: '8.0',
    captured_at: '2026-10-21T17:00:00Z',
    ...overrides,
  };
}
