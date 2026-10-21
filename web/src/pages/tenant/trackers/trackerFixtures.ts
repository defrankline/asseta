import type { MachineDto, TrackerDto } from '../../../api/types';

export const TRACKER_ID = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
export const MACHINE_ID = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';

export function makeTracker(overrides: Partial<TrackerDto> = {}): TrackerDto {
  return {
    id: TRACKER_ID,
    tracker_model_id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
    adapter: 'TRACCAR',
    external_id: '356938035643809',
    label: 'TRK-01',
    sim_iccid: null,
    sim_msisdn: '+255700000001',
    carrier: 'Vodacom',
    provisioning_state: 'VERIFIED_REPORTING',
    first_report_at: '2026-10-01T08:00:00Z',
    last_report_at: '2026-10-21T09:00:00Z',
    capabilities: [
      {
        capability: 'GNSS',
        declared: true,
        verified_at: '2026-10-01T08:00:00Z',
        last_observed_at: '2026-10-21T09:00:00Z',
      },
      { capability: 'IGNITION', declared: true, verified_at: null, last_observed_at: null },
    ],
    current_assignment: null,
    ...overrides,
  };
}

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
  created_at: '2026-09-01T00:00:00Z',
};
