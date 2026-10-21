import type {
  ApprovalRequestDto,
  CashHandoverDto,
  CashReconciliationDayDto,
  CustomerDto,
  CustomerPaymentDto,
  ExpenseDto,
  HireInvoiceDto,
  StaffDto,
} from '../api/types';
import { makeMe } from './fixtures';

/** The signed-in user in renderWithProviders (segregation-of-duties checks compare against it). */
export const ME = makeMe().user_id;
export const OTHER_USER = '44444444-4444-4444-8444-444444444444';
export const CUSTOMER_ID = 'eeeeeeee-0000-4000-8000-000000000001';
export const STAFF_ID = '55555555-0000-4000-8000-000000000001';

export const page = <T>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25 });

export const CUSTOMER: CustomerDto = {
  id: CUSTOMER_ID,
  code: 'ACME',
  name: 'Acme Builders',
  tax_id: null,
  contact_name: null,
  contact_phone: null,
  contact_email: null,
  payment_terms_days: 30,
  is_active: true,
  deactivated_at: null,
  deactivation_reason: null,
  version: 1,
};

export const SUPERVISOR: StaffDto = {
  id: STAFF_ID,
  full_name: 'Sam Supervisor',
  kind: 'SUPERVISOR',
  employee_code: null,
  phone: null,
  keycloak_subject: null,
  is_active: true,
  deactivated_at: null,
  deactivation_reason: null,
  version: 1,
};

export function makeInvoice(overrides: Partial<HireInvoiceDto> = {}): HireInvoiceDto {
  return {
    id: 'ffffffff-0000-4000-8000-000000000001',
    customer_id: CUSTOMER_ID,
    invoice_number: 'HINV-2026-00001',
    status: 'ISSUED',
    currency: 'TZS',
    subtotal: '1200000.0000',
    discount_total: '0.0000',
    tax_total: '216000.0000',
    total: '1416000.0000',
    amount_paid: '400000.0000',
    balance: '1016000.0000',
    payment_state: 'PARTIALLY_PAID',
    due_date: '2026-11-20',
    notes: null,
    created_at: '2026-10-20T08:00:00Z',
    issued_at: '2026-10-21T08:00:00Z',
    voided_at: null,
    void_reason: null,
    job_ids: ['dddddddd-0000-4000-8000-000000000001'],
    lines: [
      {
        line_no: 1,
        kind: 'HIRE',
        job_id: 'dddddddd-0000-4000-8000-000000000001',
        machine_id: 'aaaaaaaa-0000-4000-8000-000000000001',
        description: 'Excavator hire 8 h',
        quantity: '8.00',
        unit_price: '150000.0000',
        amount: '1200000.0000',
      },
    ],
    ...overrides,
  };
}

export function makePayment(overrides: Partial<CustomerPaymentDto> = {}): CustomerPaymentDto {
  return {
    id: '66666666-0000-4000-8000-000000000001',
    customer_id: CUSTOMER_ID,
    client_id: null,
    amount: '500000.0000',
    currency: 'TZS',
    method: 'BANK',
    reference: 'TRX-1',
    received_at: '2026-10-21T09:00:00Z',
    received_by_staff_id: null,
    status: 'CLAIMED',
    note: null,
    source: 'API',
    recorded_by: OTHER_USER,
    recorded_at: '2026-10-21T09:05:00Z',
    verified_by: null,
    verified_at: null,
    decision_note: null,
    allocations: [],
    ...overrides,
  };
}

export function makeHandover(overrides: Partial<CashHandoverDto> = {}): CashHandoverDto {
  return {
    id: '77777777-0000-4000-8000-000000000001',
    client_id: null,
    staff_member_id: STAFF_ID,
    amount: '90000.0000',
    currency: 'TZS',
    handed_at: '2026-10-21T15:00:00Z',
    reference: 'SLIP-9',
    note: null,
    status: 'CLAIMED',
    source: 'MOBILE',
    recorded_by: OTHER_USER,
    recorded_at: '2026-10-21T15:01:00Z',
    verified_by: null,
    verified_at: null,
    decision_note: null,
    ...overrides,
  };
}

export function makeDay(
  overrides: Partial<CashReconciliationDayDto> = {},
): CashReconciliationDayDto {
  return {
    day: '2026-10-21',
    opening: '100000.0000',
    floats_issued: '50000.0000',
    collections: '200000.0000',
    approved_spending: '30000.0000',
    verified_handovers: '120000.0000',
    outstanding: '200000.0000',
    claimed_unverified_handovers: '90000.0000',
    pending_spending: '15000.0000',
    unverified_collections: '40000.0000',
    outstanding_if_claims_verified: '110000.0000',
    ...overrides,
  };
}

export function makeExpense(overrides: Partial<ExpenseDto> = {}): ExpenseDto {
  return {
    id: '88888888-0000-4000-8000-000000000001',
    client_id: null,
    category_id: 'abababab-abab-4bab-8bab-abababababab',
    supplier: 'Shell',
    description: 'Diesel for EX-01',
    amount: '250000.0000',
    currency: 'TZS',
    incurred_at: '2026-10-21T07:00:00Z',
    machine_id: null,
    job_id: null,
    paid_from: 'CASH_CUSTODY',
    custodian_staff_id: STAFF_ID,
    status: 'PENDING_APPROVAL',
    policy_version: 'EC:T3',
    receipt_required: true,
    gps_status: 'FIX',
    latitude: -6.8,
    longitude: 39.28,
    gps_accuracy_m: 12,
    source: 'MOBILE',
    submitted_by: OTHER_USER,
    submitted_at: '2026-10-21T07:05:00Z',
    decided_by: null,
    decided_at: null,
    decision_note: null,
    receipt_attachment_ids: ['99999999-0000-4000-8000-000000000001'],
    approval_request_id: '12121212-0000-4000-8000-000000000001',
    ...overrides,
  };
}

export function makeApproval(overrides: Partial<ApprovalRequestDto> = {}): ApprovalRequestDto {
  return {
    id: '12121212-0000-4000-8000-000000000001',
    subject_type: 'EXPENSE',
    subject_id: '88888888-0000-4000-8000-000000000001',
    amount: '250000.0000',
    currency: 'TZS',
    reason: 'Amount 250000 TZS exceeds the auto-approval limit (100000)',
    policy_version: 'EC:T3',
    status: 'PENDING',
    requested_by: OTHER_USER,
    requested_at: '2026-10-21T07:05:00Z',
    decided_by: null,
    decided_at: null,
    decision_note: null,
    ...overrides,
  };
}
