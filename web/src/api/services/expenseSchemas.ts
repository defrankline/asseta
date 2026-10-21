import { object, type Schema } from 'yup';
import type {
  ApprovalRequestDto,
  ApprovalStatus,
  ExpenseCategoryDto,
  ExpenseDto,
  ExpensePaidFrom,
  ExpenseStatus,
  FuelEventDto,
  FuelEventType,
  GatewayCreatedDto,
  GatewayDto,
} from '../types';
import {
  bool,
  id,
  idList,
  int,
  nullableId,
  nullableNum,
  nullableText,
  oneOf,
  text,
} from './schemaKit';

export const expenseCategorySchema: Schema<ExpenseCategoryDto> = object({
  id: id(),
  code: text(),
  name: text(),
  is_active: bool(),
  sync_revision: int(),
  deactivated_at: nullableText().default(null),
  deactivation_reason: nullableText().default(null),
  version: int(),
});

export const gatewaySchema: Schema<GatewayDto> = object({
  id: id(),
  name: text(),
  adapter: oneOf(['TRACCAR'] as const),
  active: bool(),
  last_seen_at: nullableText(),
  created_at: text(),
});

export const gatewayCreatedSchema: Schema<GatewayCreatedDto> = object({
  id: id(),
  name: text(),
  adapter: oneOf(['TRACCAR'] as const),
  gateway_key: text(),
});

// ---- Field expenses, fuel events and approval requests (Gate 5) ----

export const EXPENSE_STATUSES: readonly ExpenseStatus[] = [
  'PENDING_APPROVAL',
  'APPROVED',
  'REJECTED',
];
export const PAID_FROM_VALUES: readonly ExpensePaidFrom[] = ['CASH_CUSTODY', 'COMPANY'];
export const FUEL_EVENT_TYPES: readonly FuelEventType[] = ['PURCHASE', 'ISSUE', 'USAGE'];
export const APPROVAL_STATUSES: readonly ApprovalStatus[] = ['PENDING', 'APPROVED', 'REJECTED'];

export const expenseSchema: Schema<ExpenseDto> = object({
  id: id(),
  client_id: nullableId(),
  category_id: id(),
  supplier: nullableText(),
  description: text(),
  amount: text(),
  currency: text(),
  incurred_at: text(),
  machine_id: nullableId(),
  job_id: nullableId(),
  paid_from: oneOf(PAID_FROM_VALUES),
  custodian_staff_id: nullableId(),
  status: oneOf(EXPENSE_STATUSES),
  policy_version: text(),
  receipt_required: bool(),
  gps_status: nullableText(),
  latitude: nullableNum(),
  longitude: nullableNum(),
  gps_accuracy_m: nullableNum(),
  source: text(),
  submitted_by: nullableId(),
  submitted_at: text(),
  decided_by: nullableId(),
  decided_at: nullableText(),
  decision_note: nullableText(),
  receipt_attachment_ids: idList().default([]),
  approval_request_id: nullableId().default(null),
});

export const fuelEventSchema: Schema<FuelEventDto> = object({
  id: id(),
  client_id: nullableId(),
  event_type: oneOf(FUEL_EVENT_TYPES),
  litres: text(),
  unit_price: nullableText(),
  attributed_cost: text(),
  currency: text(),
  machine_id: nullableId(),
  job_id: nullableId(),
  expense_id: nullableId(),
  meter_reading: nullableText(),
  supplier: nullableText(),
  occurred_at: text(),
  note: nullableText(),
  source: text(),
  recorded_by: nullableId(),
});

export const approvalRequestSchema: Schema<ApprovalRequestDto> = object({
  id: id(),
  subject_type: text(),
  subject_id: id(),
  amount: text(),
  currency: text(),
  reason: text(),
  policy_version: text(),
  status: oneOf(APPROVAL_STATUSES),
  requested_by: nullableId(),
  requested_at: text(),
  decided_by: nullableId(),
  decided_at: nullableText(),
  decision_note: nullableText(),
});
