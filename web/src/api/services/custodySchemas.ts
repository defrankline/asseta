/**
 * Runtime (Yup) response schemas for the cash custody chain controls (accountability design C) and the
 * oversight endpoints (design D). Money values are decimal strings and stay strings.
 */
import { array, object, type Schema } from 'yup';
import type {
  AccountabilitySummaryDto,
  CashAckMethod,
  CashDecisionStatus,
  CashReasonDto,
  CashReasonKind,
  CashRetentionDto,
  CashTransferDto,
  CashTransferStatus,
  CashVarianceDto,
  CountAmountDto,
  CustodianDto,
  CustodyAdjustmentDto,
  CustodyAdjustmentKind,
  CustodyTransactionDto,
  OverdueAmountDto,
  ReconciliationFigure,
  RemittanceOverdueDto,
  SecurityEventDto,
  SecurityEventKind,
  SyncConflictDto,
  SyncResolutionOutcome,
  VarianceOutcome,
  VarianceSource,
  VarianceStatus,
} from '../custodyTypes';
import {
  bool,
  id,
  int,
  nullableId,
  nullableInt,
  nullableOneOf,
  nullableRecord,
  nullableText,
  oneOf,
  record,
  text,
} from './schemaKit';

export const STAFF_KINDS = ['SUPERVISOR', 'OPERATOR', 'OTHER'] as const;
/** DEC-031: a negative variance (more received than declared) is a surplus to explain. */
export const VARIANCE_KINDS = ['SHORTFALL', 'SURPLUS'] as const;
export const OVERDUE_REASONS = ['CUTOFF', 'HELD_TOO_LONG'] as const;
export const TRANSFER_STATUSES: readonly CashTransferStatus[] = [
  'PENDING_ACKNOWLEDGEMENT',
  'ACKNOWLEDGED',
  'DISPUTED',
];
export const ACK_METHODS: readonly CashAckMethod[] = [
  'RECEIVER',
  'ON_BEHALF',
  'RECORDER_IS_RECEIVER',
  'NOT_REQUIRED',
];
export const VARIANCE_SOURCES: readonly VarianceSource[] = ['TRANSFER', 'REMITTANCE', 'FLOAT'];
export const VARIANCE_STATUSES: readonly VarianceStatus[] = [
  'OPEN',
  'WRITE_OFF_PROPOSED',
  'RESOLVED',
];
export const VARIANCE_OUTCOMES: readonly VarianceOutcome[] = [
  'RECOVERED',
  'CORRECTED_ERROR',
  'WRITTEN_OFF',
];
export const DECISION_STATUSES: readonly CashDecisionStatus[] = ['PENDING', 'APPROVED', 'REJECTED'];
export const ADJUSTMENT_KINDS: readonly CustodyAdjustmentKind[] = ['REVERSAL', 'ADJUSTMENT'];
export const REASON_KINDS: readonly CashReasonKind[] = [
  'VARIANCE',
  'WRITE_OFF',
  'RETENTION',
  'ADJUSTMENT',
];
export const FIGURES: readonly ReconciliationFigure[] = [
  'floats_issued',
  'collections',
  'transfers_in',
  'transfers_out',
  'approved_spending',
  'verified_handovers',
  'adjustments',
  'written_off',
  'claimed_unverified_handovers',
  'pending_spending',
  'unverified_collections',
  'in_transit_out',
  'in_transit_in',
  'pending_floats',
  'pending_adjustments',
];
export const SECURITY_EVENT_KINDS: readonly SecurityEventKind[] = [
  'PERMISSION_DENIED',
  'SEGREGATION_OF_DUTIES',
];
export const SYNC_OUTCOMES: readonly SyncResolutionOutcome[] = ['DISMISSED', 'RECAPTURED'];

export const custodianSchema: Schema<CustodianDto> = object({
  staff_member_id: id(),
  full_name: text(),
  kind: oneOf(STAFF_KINDS),
  employee_code: nullableText(),
  is_active: bool(),
  has_login: bool(),
});

export const transferSchema: Schema<CashTransferDto> = object({
  id: id(),
  client_id: nullableId(),
  from_staff_id: id(),
  to_staff_id: id(),
  amount_declared: text(),
  currency: text(),
  transferred_at: text(),
  note: nullableText(),
  status: oneOf(TRANSFER_STATUSES),
  source: text(),
  recorded_by: nullableId(),
  recorded_at: text(),
  amount_received: nullableText(),
  ack_method: nullableOneOf(ACK_METHODS),
  acknowledged_by: nullableId(),
  acknowledged_at: nullableText(),
  ack_note: nullableText(),
  variance_id: nullableId().default(null),
});

export const varianceSchema: Schema<CashVarianceDto> = object({
  id: id(),
  source_type: oneOf(VARIANCE_SOURCES),
  source_id: id(),
  staff_member_id: nullableId(),
  counterparty_staff_id: nullableId(),
  currency: text(),
  declared_amount: text(),
  received_amount: text(),
  amount: text(),
  kind: oneOf(VARIANCE_KINDS).default('SHORTFALL'),
  case_id: nullableId(),
  opened_at: text(),
  opened_by: nullableId(),
  status: oneOf(VARIANCE_STATUSES),
  reason_id: nullableId(),
  proposed_by: nullableId(),
  proposed_at: nullableText(),
  proposal_note: nullableText(),
  outcome: nullableOneOf(VARIANCE_OUTCOMES),
  resolved_by: nullableId(),
  resolved_at: nullableText(),
  resolution_note: nullableText(),
});

export const retentionSchema: Schema<CashRetentionDto> = object({
  id: id(),
  staff_member_id: id(),
  amount: text(),
  currency: text(),
  reason_id: nullableId(),
  reason: text(),
  valid_until: nullableText(),
  status: oneOf(DECISION_STATUSES),
  created_by: nullableId(),
  created_at: text(),
  decided_by: nullableId(),
  decided_at: nullableText(),
  decision_note: nullableText(),
});

export const adjustmentSchema: Schema<CustodyAdjustmentDto> = object({
  id: id(),
  staff_member_id: id(),
  kind: oneOf(ADJUSTMENT_KINDS),
  amount: text(),
  currency: text(),
  occurred_at: text(),
  reason_id: nullableId(),
  reason: text(),
  reverses_entity_type: nullableText(),
  reverses_entity_id: nullableId(),
  status: oneOf(DECISION_STATUSES),
  created_by: nullableId(),
  created_at: text(),
  decided_by: nullableId(),
  decided_at: nullableText(),
  decision_note: nullableText(),
});

export const reasonSchema: Schema<CashReasonDto> = object({
  id: id(),
  kind: oneOf(REASON_KINDS),
  label: text(),
  description: nullableText(),
  is_active: bool(),
  version: int(),
  created_at: text(),
  deactivated_at: nullableText(),
  deactivation_reason: nullableText(),
});

export const custodyTransactionSchema: Schema<CustodyTransactionDto> = object({
  figure: oneOf(FIGURES),
  occurred_at: text(),
  amount: text(),
  currency: text(),
  entity_type: text(),
  entity_id: id(),
  status: text(),
  reference: nullableText(),
  note: nullableText(),
  recorded_by: nullableId(),
  counterparty_staff_id: nullableId(),
});

export const securityEventSchema: Schema<SecurityEventDto> = object({
  id: id(),
  occurred_at: text(),
  kind: oneOf(SECURITY_EVENT_KINDS),
  actor_user_id: nullableId(),
  actor_subject: nullableText(),
  actor_display_name: nullableText().default(null),
  permission: nullableText(),
  action: nullableText(),
  entity_type: nullableText(),
  entity_id: nullableText(),
  request_method: nullableText(),
  request_path: nullableText(),
  detail: record(),
});

export const syncConflictSchema: Schema<SyncConflictDto> = object({
  operation_id: id(),
  op_type: text(),
  status: oneOf(['CONFLICT', 'REJECTED'] as const),
  error_code: nullableText(),
  error_message: nullableText(),
  server_state: record(),
  payload: record(),
  created_at_device: text(),
  received_at: text(),
  attempts: int(),
  device_id: text(),
  device_platform: text(),
  submitted_by: id(),
  submitted_by_name: nullableText(),
  resolution: object({
    id: id(),
    outcome: oneOf(SYNC_OUTCOMES),
    reason: text(),
    recaptured_entity_type: nullableText(),
    recaptured_entity_id: nullableId(),
    resolved_by: nullableId(),
    resolved_at: text(),
  })
    .nullable()
    .defined(),
});

const countAmountSchema: Schema<CountAmountDto> = object({
  currency: text(),
  count: int(),
  amount: text(),
});
const countAmounts = () => array(countAmountSchema).required();

export const accountabilitySummarySchema: Schema<AccountabilitySummaryDto> = object({
  as_of: text(),
  policy_version: text(),
  hidden_tiles: array(text()).required(),
  unavailable_tiles: array(text()).required(),
  customer_hours: nullableRecord().default(null),
  hours_awaiting_activation: nullableRecord().default(null),
  engine_hours: nullableRecord().default(null),
  unexplained_hours: nullableRecord().default(null),
  missing_daily_reports: nullableRecord().default(null),
  revenue_differences: nullableRecord().default(null),
  investigations: object({ open: int(), in_review: int() }).nullable().default(null),
  cash: object({
    custodians: array(
      object({
        staff_member_id: id(),
        staff_name: text(),
        currency: text(),
        outstanding: text(),
        in_transit_out: text(),
        claimed_unverified_handovers: text(),
        pending_floats: text(),
      }),
    ).required(),
    transfers_awaiting_acknowledgement: countAmounts(),
    floats_awaiting_acknowledgement: countAmounts(),
    remittances_awaiting_confirmation: countAmounts(),
    partial_remittances_in_window: int(),
  })
    .nullable()
    .default(null),
  payments: object({ awaiting_confirmation: countAmounts() }).nullable().default(null),
  discrepancies: object({
    open_variances: countAmounts(),
    write_offs_proposed: int(),
    sync_conflicts_unresolved: int(),
  })
    .nullable()
    .default(null),
  unauthorized_attempts: object({
    window_days: int(),
    permission_denied: int(),
    segregation_of_duties: int(),
  })
    .nullable()
    .default(null),
  outstanding_approvals: object({
    approval_requests: int(),
    cash_retentions: int(),
    custody_adjustments: int(),
    write_offs: int(),
    payments_to_verify: int(),
    remittances_to_verify: int(),
    total: int(),
  })
    .nullable()
    .default(null),
});

const overdueAmountSchema: Schema<OverdueAmountDto> = object({
  amount: text(),
  currency: text(),
});

/** A custodian flagged for holding unremitted cash past the tenant's daily cut-off (G4). */
export const remittanceOverdueSchema: Schema<RemittanceOverdueDto> = object({
  id: id(),
  staff_member_id: id(),
  staff_member_name: nullableText().optional(),
  local_day: text(),
  cutoff_hour: int(),
  amounts: array(overdueAmountSchema).required(),
  flagged_at: text(),
  policy_version: text(),
  reason: oneOf(OVERDUE_REASONS).default('CUTOFF'),
  held_since: nullableText().optional(),
  max_holding_days: nullableInt().optional(),
});
