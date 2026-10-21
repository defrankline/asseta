import { mixed, object, string, type ObjectSchema } from 'yup';
import type {
  MachineCreateIn,
  MachineDto,
  MachineStatus,
  MachineUpdateIn,
  Ownership,
} from '../../../api/types';
import { MACHINE_STATUSES, OWNERSHIPS } from '../../../api/services/fleetSchemas';

/**
 * Machine form values. Field names equal the API field names so server `details[].field`
 * errors land on the matching Formik field. Everything is a string while editing.
 */
export interface MachineFormValues {
  asset_code: string;
  name: string;
  manufacturer: string;
  model: string;
  serial_number: string;
  year_of_manufacture: string;
  category_id: string;
  operating_area_id: string;
  ownership: Ownership;
  status: MachineStatus;
  meter_decimal_places: string;
  capacity_value: string;
  capacity_unit: string;
}

export const IDENTITY_FIELDS = [
  'asset_code',
  'name',
  'manufacturer',
  'model',
  'serial_number',
  'year_of_manufacture',
] as const;
export const EDIT_IDENTITY_FIELDS = [...IDENTITY_FIELDS.slice(1), 'status'] as const;
export const CLASSIFICATION_FIELDS = ['category_id', 'operating_area_id', 'ownership'] as const;
export const METERING_FIELDS = ['meter_decimal_places', 'capacity_value', 'capacity_unit'] as const;

export const METER_DP_OPTIONS = [
  { value: '0', label: '0 (whole hours)' },
  { value: '1', label: '1 (0.1 h)' },
  { value: '2', label: '2 (0.01 h)' },
] as const;

export function emptyMachineValues(): MachineFormValues {
  return {
    asset_code: '',
    name: '',
    manufacturer: '',
    model: '',
    serial_number: '',
    year_of_manufacture: '',
    category_id: '',
    operating_area_id: '',
    ownership: 'OWNED',
    status: 'ACTIVE',
    meter_decimal_places: '1',
    capacity_value: '',
    capacity_unit: '',
  };
}

export function valuesFromMachine(m: MachineDto): MachineFormValues {
  return {
    asset_code: m.asset_code,
    name: m.name,
    manufacturer: m.manufacturer ?? '',
    model: m.model ?? '',
    serial_number: m.serial_number ?? '',
    year_of_manufacture: m.year_of_manufacture === null ? '' : String(m.year_of_manufacture),
    category_id: m.category_id ?? '',
    operating_area_id: m.operating_area_id ?? '',
    ownership: m.ownership,
    status: m.status,
    meter_decimal_places: String(m.meter_decimal_places),
    capacity_value: m.capacity_value ?? '',
    capacity_unit: m.capacity_unit ?? '',
  };
}

const opt = (label: string, max: number) =>
  string()
    .trim()
    .max(max, `${label} must be at most ${String(max)} characters`)
    .ensure();

const baseShape = {
  name: string()
    .trim()
    .required('Name is required')
    .max(200, 'Name must be at most 200 characters'),
  manufacturer: opt('Manufacturer', 100),
  model: opt('Model', 100),
  serial_number: opt('Serial number', 100),
  year_of_manufacture: string()
    .trim()
    .ensure()
    .test(
      'year',
      'Year must be between 1950 and 2100',
      (v) => v === '' || (/^\d{4}$/.test(v) && Number(v) >= 1950 && Number(v) <= 2100),
    ),
  category_id: string().ensure(),
  operating_area_id: string().ensure(),
  ownership: mixed<Ownership>().oneOf(OWNERSHIPS).required('Ownership is required'),
  status: mixed<MachineStatus>().oneOf(MACHINE_STATUSES).required('Status is required'),
  meter_decimal_places: string()
    .required('Meter precision is required')
    .oneOf(['0', '1', '2'], 'Meter precision must be 0, 1 or 2 decimal places'),
  capacity_value: string()
    .trim()
    .ensure()
    .matches(/^(\d+(\.\d{1,4})?)?$/, 'Capacity must be a number with at most 4 decimal places'),
  capacity_unit: opt('Capacity unit', 20),
};

export const createMachineSchema: ObjectSchema<MachineFormValues> = object({
  asset_code: string()
    .trim()
    .required('Asset code is required')
    .max(64, 'Asset code must be at most 64 characters'),
  ...baseShape,
});

export const editMachineSchema: ObjectSchema<MachineFormValues> = object({
  asset_code: string().ensure(),
  ...baseShape,
});

const orNull = (v: string): string | null => (v.trim() === '' ? null : v.trim());

function common(v: MachineFormValues) {
  return {
    name: v.name.trim(),
    manufacturer: orNull(v.manufacturer),
    model: orNull(v.model),
    serial_number: orNull(v.serial_number),
    year_of_manufacture: v.year_of_manufacture.trim() === '' ? null : Number(v.year_of_manufacture),
    category_id: orNull(v.category_id),
    operating_area_id: orNull(v.operating_area_id),
    ownership: v.ownership,
    meter_decimal_places: Number(v.meter_decimal_places),
    // Kept as a decimal string (never parsed to float).
    capacity_value: orNull(v.capacity_value),
    capacity_unit: orNull(v.capacity_unit),
  };
}

export function toCreatePayload(v: MachineFormValues): MachineCreateIn {
  return { asset_code: v.asset_code.trim(), ...common(v) };
}

export function toUpdatePayload(v: MachineFormValues, version: number): MachineUpdateIn {
  return { ...common(v), status: v.status, version };
}
