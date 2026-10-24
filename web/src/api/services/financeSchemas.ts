/**
 * Runtime (Yup) response schemas for tenant hire finance: hire invoices, customer payments and
 * allocations, balances, statements, cash custody, handovers, reconciliation and profitability.
 * Money values are decimal strings and stay strings.
 */
import { array, mixed, object, string, type Schema } from 'yup';
import type {
  CashCustodyBalanceDto,
  CashCustodyEntryDto,
  CashHandoverDto,
  CashReconciliationDto,
  CashSupervisorSummaryDto,
  ChargeKind,
  CustodyEntryType,
  CustomerBalanceDto,
  CustomerPaymentDto,
  CustomerStatementDto,
  HireInvoiceDto,
  HireInvoiceStatus,
  HirePaymentMethod,
  InvoicePaymentState,
  ProfitabilityDto,
  ProfitabilityGroupBy,
  SettlementStatus,
  StatementLineKind,
} from '../types';
import { id, idList, int, nullableId, nullableOneOf, nullableText, oneOf, text } from './schemaKit';

export const HIRE_INVOICE_STATUSES: readonly HireInvoiceStatus[] = ['DRAFT', 'ISSUED', 'VOIDED'];
export const CHARGE_KINDS: readonly ChargeKind[] = [
  'HIRE',
  'STANDBY',
  'MOBILIZATION',
  'DISCOUNT',
  'TAX',
];
export const PAYMENT_STATES: readonly InvoicePaymentState[] = ['UNPAID', 'PARTIALLY_PAID', 'PAID'];
export const PAYMENT_METHODS: readonly HirePaymentMethod[] = ['CASH', 'BANK', 'MOBILE_MONEY'];
export const SETTLEMENT_STATUSES: readonly SettlementStatus[] = ['CLAIMED', 'VERIFIED', 'REJECTED'];
export const STATEMENT_KINDS: readonly StatementLineKind[] = ['INVOICE', 'REVERSAL', 'PAYMENT'];
export const CUSTODY_ENTRY_TYPES: readonly CustodyEntryType[] = ['OPENING_BALANCE', 'FLOAT_ISSUED'];
export const GROUP_BYS: readonly ProfitabilityGroupBy[] = ['MACHINE', 'JOB', 'CUSTOMER'];

export const hireInvoiceSchema: Schema<HireInvoiceDto> = object({
  id: id(),
  customer_id: id(),
  invoice_number: nullableText(),
  status: oneOf(HIRE_INVOICE_STATUSES),
  currency: text(),
  subtotal: text(),
  discount_total: text(),
  tax_total: text(),
  total: text(),
  amount_paid: text(),
  balance: text(),
  payment_state: nullableOneOf(PAYMENT_STATES),
  due_date: nullableText(),
  notes: nullableText(),
  created_at: text(),
  issued_at: nullableText(),
  voided_at: nullableText(),
  void_reason: nullableText(),
  job_ids: idList(),
  lines: array(
    object({
      line_no: int(),
      kind: oneOf(CHARGE_KINDS),
      job_id: id(),
      machine_id: id(),
      description: text(),
      quantity: text(),
      unit_price: text(),
      amount: text(),
    }),
  ).required(),
});

const allocationSchema = object({
  id: id(),
  invoice_id: id(),
  amount: text(),
  created_at: text(),
  released_at: nullableText(),
  release_reason: nullableText(),
});

export const customerPaymentSchema: Schema<CustomerPaymentDto> = object({
  id: id(),
  customer_id: id(),
  client_id: nullableId(),
  amount: text(),
  currency: text(),
  method: oneOf(PAYMENT_METHODS),
  reference: nullableText(),
  received_at: text(),
  received_by_staff_id: nullableId(),
  status: oneOf(SETTLEMENT_STATUSES),
  note: nullableText(),
  source: text(),
  recorded_by: nullableId(),
  recorded_at: text(),
  verified_by: nullableId(),
  verified_at: nullableText(),
  decision_note: nullableText(),
  allocations: array(allocationSchema).default([]),
});

export const customerBalanceSchema: Schema<CustomerBalanceDto> = object({
  customer_id: id(),
  currency: text(),
  invoiced: text(),
  reversed: text(),
  verified_payments: text(),
  balance: text(),
  unallocated_credit: text(),
  claimed_unverified: text(),
  open_invoices: int(),
});

export const customerStatementSchema: Schema<CustomerStatementDto> = object({
  customer_id: id(),
  currency: text(),
  period_from: text(),
  period_to: text(),
  opening_balance: text(),
  lines: array(
    object({
      at: text(),
      kind: oneOf(STATEMENT_KINDS),
      reference: text(),
      description: text(),
      debit: text(),
      credit: text(),
      running_balance: text(),
    }),
  ).required(),
  total_debits: text(),
  total_credits: text(),
  closing_balance: text(),
  claimed_unverified: array(customerPaymentSchema).required(),
  claimed_unverified_total: text(),
});

export const custodyEntrySchema: Schema<CashCustodyEntryDto> = object({
  id: id(),
  staff_member_id: id(),
  entry_type: oneOf(CUSTODY_ENTRY_TYPES),
  amount: text(),
  currency: text(),
  occurred_at: text(),
  reference: nullableText(),
  note: nullableText(),
});

export const custodyBalanceSchema: Schema<CashCustodyBalanceDto> = object({
  staff_member_id: id(),
  currency: text(),
  outstanding: text(),
  claimed_unverified_handovers: text(),
  pending_spending: text(),
  as_of: text(),
});

export const handoverSchema: Schema<CashHandoverDto> = object({
  id: id(),
  client_id: nullableId(),
  staff_member_id: id(),
  amount: text(),
  currency: text(),
  handed_at: text(),
  reference: nullableText(),
  note: nullableText(),
  status: oneOf(SETTLEMENT_STATUSES),
  source: text(),
  recorded_by: nullableId(),
  recorded_at: text(),
  verified_by: nullableId(),
  verified_at: nullableText(),
  decision_note: nullableText(),
});

export const reconciliationSchema: Schema<CashReconciliationDto> = object({
  staff_member_id: id(),
  currency: text(),
  timezone: text(),
  days: array(
    object({
      day: text(),
      opening: text(),
      floats_issued: text(),
      collections: text(),
      approved_spending: text(),
      verified_handovers: text(),
      outstanding: text(),
      claimed_unverified_handovers: text(),
      pending_spending: text(),
      unverified_collections: text(),
      outstanding_if_claims_verified: text(),
    }),
  ).required(),
});

export const supervisorSummarySchema: Schema<CashSupervisorSummaryDto> = object({
  staff_member_id: id(),
  staff_name: text(),
  currency: text(),
  period_from: text(),
  period_to: text(),
  opening: text(),
  floats_issued: text(),
  collections: text(),
  approved_spending: text(),
  verified_handovers: text(),
  closing_outstanding: text(),
  claimed_unverified_handovers: text(),
  pending_spending: text(),
  unverified_collections: text(),
});

function isStringRecord(value: unknown): value is Record<string, string> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    Object.values(value).every((v) => typeof v === 'string')
  );
}

export const profitabilitySchema: Schema<ProfitabilityDto> = object({
  group_by: oneOf(GROUP_BYS),
  period_from: text(),
  period_to: text(),
  timezone: text(),
  rows: array(
    object({
      group_key: string().nullable().defined(),
      label: text(),
      currency: text(),
      revenue: text(),
      reversed_revenue: text(),
      net_revenue: text(),
      expense_cost: text(),
      fuel_cost: text(),
      direct_cost: text(),
      margin: text(),
      cost_by_category: mixed<Record<string, string>>(isStringRecord).required(),
    }),
  ).required(),
});
