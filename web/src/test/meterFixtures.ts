import type { ExceptionDto, MachineDto, MeterCaptureDto, ResetDto } from '../api/types';

export const MACHINE_ID = 'aaaaaaaa-0000-4000-8000-000000000001';

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
    machine_id: MACHINE_ID,
    kind: 'DAILY',
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
