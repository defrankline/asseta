import type { MachineDto } from '../../../api/types';

export function makeMachine(overrides: Partial<MachineDto> = {}): MachineDto {
  return {
    id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    asset_code: 'EX-01',
    name: 'Excavator 1',
    category_id: null,
    operating_area_id: null,
    manufacturer: 'CAT',
    model: '320',
    serial_number: null,
    year_of_manufacture: 2019,
    capacity_value: '20.0000',
    capacity_unit: 't',
    meter_decimal_places: 1,
    ownership: 'OWNED',
    status: 'ACTIVE',
    version: 3,
    created_at: '2026-09-01T08:00:00Z',
    billing_enrolled: false,
    primary_tracker_id: null,
    primary_tracker_label: null,
    ...overrides,
  };
}
