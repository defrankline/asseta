/** Runtime (Yup) response schemas for the tenant equipment registry and staff endpoints. */
import { object, type Schema } from 'yup';
import type {
  AreaDto,
  AssignmentDto,
  AssignmentRole,
  CategoryDto,
  MachineDto,
  MachineStatus,
  Ownership,
  StaffDto,
  StaffKind,
} from '../types';
import {
  bool,
  id,
  int,
  nullableId,
  nullableInt,
  nullableText,
  oneOf,
  text,
  lifecycleFields,
} from './schemaKit';

export const MACHINE_STATUSES: readonly MachineStatus[] = ['ACTIVE', 'OUT_OF_SERVICE', 'DISPOSED'];
export const OWNERSHIPS: readonly Ownership[] = ['OWNED', 'LEASED', 'HIRED_IN'];
export const STAFF_KINDS: readonly StaffKind[] = ['SUPERVISOR', 'OPERATOR', 'OTHER'];
export const ASSIGNMENT_ROLES: readonly AssignmentRole[] = ['SUPERVISOR', 'OPERATOR'];

export const machineSchema: Schema<MachineDto> = object({
  id: id(),
  asset_code: text(),
  name: text(),
  category_id: nullableId(),
  operating_area_id: nullableId(),
  manufacturer: nullableText(),
  model: nullableText(),
  serial_number: nullableText(),
  year_of_manufacture: nullableInt(),
  capacity_value: nullableText(),
  capacity_unit: nullableText(),
  meter_decimal_places: int(),
  ownership: oneOf(OWNERSHIPS),
  status: oneOf(MACHINE_STATUSES),
  version: int(),
  created_at: text(),
  deactivated_at: nullableText().default(null),
  deactivation_reason: nullableText().default(null),
  billing_enrolled: bool(),
  primary_tracker_id: nullableId(),
  primary_tracker_label: nullableText(),
});

export const categorySchema: Schema<CategoryDto> = object({
  id: id(),
  name: text(),
  description: nullableText(),
  is_active: bool(),
  ...lifecycleFields(),
});

export const areaSchema: Schema<AreaDto> = object({
  id: id(),
  code: text(),
  name: text(),
  is_active: bool(),
  ...lifecycleFields(),
});

export const staffSchema: Schema<StaffDto> = object({
  id: id(),
  full_name: text(),
  kind: oneOf(STAFF_KINDS),
  employee_code: nullableText(),
  phone: nullableText(),
  keycloak_subject: nullableText(),
  is_active: bool(),
  ...lifecycleFields(),
});

export const assignmentSchema: Schema<AssignmentDto> = object({
  id: id(),
  machine_id: id(),
  staff_member_id: id(),
  role: oneOf(ASSIGNMENT_ROLES),
  effective_from: text(),
  effective_to: nullableText(),
});
