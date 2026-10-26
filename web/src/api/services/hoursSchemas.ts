/**
 * Runtime (Yup) response schemas for customer hours (accountability design A): purchases, ledger,
 * balances, work-execution allocations, transfers, cancellations, discounts, credit arrangements,
 * reason lists, walk-in customers and payment evidence. Hours and money stay decimal strings.
 */
import { array, mixed, object, string, type ObjectSchema, type Schema } from 'yup';
import type {
  ActivationSource,
  AllocationLineDto,
  CancellationDto,
  CreditArrangementDto,
  CreditExposureDto,
  DiscountDto,
  HoursBalanceDto,
  HoursPurchaseDto,
  HoursPurchaseStatus,
  LedgerEntryDto,
  LedgerEntryType,
  MachineHoursDto,
  PaymentEvidenceDto,
  ProposalStatus,
  PurchaseAllocationDto,
  PurchaseTotalsDto,
  ReasonCodeDto,
  ReasonKind,
  RequestStatus,
  TransferDto,
  WalkInCustomerDto,
  WorkExecutionAllocationDto,
} from '../hoursTypes';
import type { CustomerPaymentDto } from '../types';
import { customerPaymentSchema } from './financeSchemas';
import { CUSTOMER_KINDS } from './jobSchemas';
import { bool, id, int, nullableId, nullableOneOf, nullableText, oneOf, text } from './schemaKit';

export const PURCHASE_STATUSES: readonly HoursPurchaseStatus[] = [
  'AWAITING_PAYMENT',
  'PARTLY_ACTIVE',
  'ACTIVE',
  'CONSUMED',
  'EXPIRED',
  'CANCELLED',
];
export const LEDGER_ENTRY_TYPES: readonly LedgerEntryType[] = [
  'ACTIVATED',
  'CONSUMED',
  'TRANSFER_OUT',
  'TRANSFER_IN',
  'EXPIRED',
  'REVERSAL',
  'PROVISIONAL',
  'PROVISIONAL_REVERSED',
];
export const ACTIVATION_SOURCES: readonly ActivationSource[] = ['PAYMENT', 'CREDIT'];
export const REQUEST_STATUSES: readonly RequestStatus[] = [
  'PENDING',
  'APPROVED',
  'REJECTED',
  'WITHDRAWN',
];
export const PROPOSAL_STATUSES: readonly ProposalStatus[] = [
  'PROPOSED',
  'APPROVED',
  'REJECTED',
  'WITHDRAWN',
  'REVOKED',
];
export const REASON_KINDS: readonly ReasonKind[] = [
  'DISCOUNT',
  'CREDIT',
  'TRANSFER',
  'CANCELLATION',
];

const optionalText = () => string().nullable().default(null);

export const purchaseAllocationSchema: Schema<PurchaseAllocationDto> = object({
  id: id(),
  purchase_id: id(),
  payment_id: id(),
  amount: text(),
  created_at: text(),
  payment_status: optionalText(),
  released_at: nullableText(),
  release_reason: nullableText(),
});

export const machineHoursSchema: Schema<MachineHoursDto> = object({
  machine_id: id(),
  activated: text(),
  consumed: text(),
  expired: text(),
  remaining: text(),
  reversed: text(),
  transferred_in: text(),
  transferred_out: text(),
  provisional: text().default('0'),
});

export const purchaseTotalsSchema: ObjectSchema<PurchaseTotalsDto> = object({
  purchased: text(),
  activated: text(),
  activated_from_payments: text(),
  activated_on_credit: text(),
  awaiting_activation: text(),
  consumed: text(),
  expired: text(),
  remaining: text(),
  reversed: text(),
  transferred: text(),
  provisional: text().default('0'),
  amount_claimed_unverified: text(),
  amount_outstanding: text(),
  amount_verified: text(),
});

export const hoursPurchaseSchema: Schema<HoursPurchaseDto> = object({
  id: id(),
  purchase_number: text(),
  customer_id: id(),
  customer_kind: nullableOneOf(CUSTOMER_KINDS).default(null),
  customer_name: optionalText(),
  machine_id: id(),
  job_site_id: nullableId(),
  hours: text(),
  currency: text(),
  rate_card_id: id(),
  hourly_rate: text(),
  discount_id: nullableId(),
  discount_percent: text(),
  effective_rate: text(),
  amount: text(),
  status: oneOf(PURCHASE_STATUSES),
  source: text(),
  note: nullableText(),
  policy_version: text(),
  client_id: nullableId(),
  created_at: text(),
  created_by: nullableId(),
  cancellation_id: nullableId(),
  cancelled_at: nullableText(),
  totals: purchaseTotalsSchema,
  allocations: array(purchaseAllocationSchema).default([]),
  machines: array(machineHoursSchema).default([]),
  payment: mixed<CustomerPaymentDto>()
    .nullable()
    .default(null)
    .test('payment', 'invalid payment', (v) => v == null || customerPaymentSchema.isValidSync(v)),
});

export const hoursBalanceSchema: Schema<HoursBalanceDto> = object({
  customer_id: id(),
  machine_id: id(),
  purchases: int(),
  activated: text(),
  awaiting_activation: text(),
  consumed: text(),
  expired: text(),
  remaining: text(),
  reversed: text(),
  transferred_in: text(),
  transferred_out: text(),
  provisional: text().default('0'),
});

export const ledgerEntrySchema: Schema<LedgerEntryDto> = object({
  id: id(),
  purchase_id: id(),
  purchase_number: optionalText(),
  customer_id: id(),
  machine_id: id(),
  entry_type: oneOf(LEDGER_ENTRY_TYPES),
  hours: text(),
  signed_hours: string().default('0'),
  occurred_at: text(),
  created_at: text(),
  created_by: nullableId(),
  activation_source: nullableOneOf(ACTIVATION_SOURCES),
  allocation_id: nullableId(),
  cancellation_id: nullableId(),
  transfer_id: nullableId(),
  payment_id: nullableId(),
  job_id: nullableId(),
  job_number: optionalText(),
  expires_at: nullableText(),
  policy_version: nullableText(),
  reason: nullableText(),
});

export const allocationLineSchema: Schema<AllocationLineDto> = object({
  entry_id: id(),
  purchase_id: id(),
  purchase_number: text(),
  hours: text(),
  occurred_at: text(),
});

export const workExecutionAllocationSchema: Schema<WorkExecutionAllocationDto> = object({
  id: id(),
  job_id: id(),
  customer_id: id(),
  machine_id: id(),
  billable_hours: text(),
  consumed_hours: text(),
  overrun_hours: text(),
  exception_id: nullableId(),
  exception_status: nullableText(),
  policy_version: text(),
  created_at: text(),
  lines: array(allocationLineSchema).required(),
});

const decisionFields = () => ({
  decided_at: nullableText(),
  decided_by: nullableId(),
  decision_note: nullableText(),
});

export const transferSchema: Schema<TransferDto> = object({
  id: id(),
  purchase_id: id(),
  from_machine_id: id(),
  to_machine_id: id(),
  hours: text(),
  reason: text(),
  reason_code_id: nullableId(),
  client_id: nullableId(),
  requested_at: text(),
  requested_by: nullableId(),
  status: oneOf(REQUEST_STATUSES),
  ...decisionFields(),
});

export const cancellationSchema: Schema<CancellationDto> = object({
  id: id(),
  purchase_id: id(),
  reason: text(),
  reason_code_id: nullableId(),
  requested_at: text(),
  requested_by: nullableId(),
  status: oneOf(REQUEST_STATUSES),
  ...decisionFields(),
});

const proposalFields = () => ({
  customer_id: id(),
  effective_from: text(),
  effective_to: nullableText(),
  reason: text(),
  reason_code_id: nullableId(),
  proposed_at: text(),
  proposed_by: nullableId(),
  status: oneOf(PROPOSAL_STATUSES),
  revoke_reason: nullableText(),
  revoked_at: nullableText(),
  revoked_by: nullableId(),
  version: int(),
  ...decisionFields(),
});

export const discountSchema: Schema<DiscountDto> = object({
  id: id(),
  percent: text(),
  ...proposalFields(),
});

export const creditArrangementSchema: Schema<CreditArrangementDto> = object({
  id: id(),
  limit_amount: text(),
  currency: text(),
  terms: nullableText(),
  ...proposalFields(),
});

export const creditExposureSchema: Schema<CreditExposureDto> = object({
  customer_id: id(),
  currency: text(),
  arrangement_id: nullableId(),
  limit_amount: nullableText(),
  exposure: text(),
  available: nullableText(),
});

export const reasonCodeSchema: Schema<ReasonCodeDto> = object({
  id: id(),
  kind: oneOf(REASON_KINDS),
  code: text(),
  label: text(),
  is_active: bool(),
  version: int(),
  deactivated_at: optionalText(),
  deactivation_reason: optionalText(),
});

export const walkInCustomerSchema: Schema<WalkInCustomerDto> = object({
  id: id(),
  code: text(),
  name: text(),
  contact_phone: nullableText(),
  kind: oneOf(CUSTOMER_KINDS),
  is_active: bool(),
  version: int(),
});

export const paymentEvidenceSchema: Schema<PaymentEvidenceDto> = object({
  id: id(),
  payment_id: id(),
  attachment_id: id(),
  created_at: text(),
  created_by: nullableId(),
});
