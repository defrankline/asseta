/** Display constants and helpers shared by the hire finance, expenses and approvals screens. */
import type {
  ApprovalStatus,
  ExpensePaidFrom,
  ExpenseStatus,
  FuelEventType,
  HireInvoiceStatus,
  HirePaymentMethod,
  InvoicePaymentState,
  SettlementStatus,
} from '../../../api/types';
import type { StatusTone } from '../../../components/display/StatusChip';
import { SUPPORTED_CURRENCIES } from '../../../utils/money';
import type { Option } from './display';

export const INVOICE_STATUS_TONES: Readonly<Record<HireInvoiceStatus, StatusTone>> = {
  DRAFT: 'info',
  ISSUED: 'success',
  VOIDED: 'default',
};
export const INVOICE_STATUS_OPTIONS: readonly Option<HireInvoiceStatus>[] = [
  { value: 'DRAFT', label: 'Draft' },
  { value: 'ISSUED', label: 'Issued' },
  { value: 'VOIDED', label: 'Voided' },
];
export const PAYMENT_STATE_TONES: Readonly<Record<InvoicePaymentState, StatusTone>> = {
  UNPAID: 'warning',
  PARTIALLY_PAID: 'info',
  PAID: 'success',
};

/** CLAIMED money is reported, not yet settled; only VERIFIED counts against balances. */
export const SETTLEMENT_TONES: Readonly<Record<SettlementStatus, StatusTone>> = {
  CLAIMED: 'warning',
  VERIFIED: 'success',
  REJECTED: 'error',
};
export const SETTLEMENT_LABELS: Readonly<Record<SettlementStatus, string>> = {
  CLAIMED: 'Claimed (unverified)',
  VERIFIED: 'Verified',
  REJECTED: 'Rejected',
};
export const SETTLEMENT_STATUS_OPTIONS: readonly Option<SettlementStatus>[] = [
  { value: 'CLAIMED', label: 'Claimed (unverified)' },
  { value: 'VERIFIED', label: 'Verified' },
  { value: 'REJECTED', label: 'Rejected' },
];

export const PAYMENT_METHOD_OPTIONS: readonly Option<HirePaymentMethod>[] = [
  { value: 'CASH', label: 'Cash' },
  { value: 'BANK', label: 'Bank transfer' },
  { value: 'MOBILE_MONEY', label: 'Mobile money' },
];
export const PAYMENT_METHOD_LABELS: Readonly<Record<HirePaymentMethod, string>> = {
  CASH: 'Cash',
  BANK: 'Bank transfer',
  MOBILE_MONEY: 'Mobile money',
};

export const EXPENSE_STATUS_TONES: Readonly<Record<ExpenseStatus, StatusTone>> = {
  PENDING_APPROVAL: 'warning',
  APPROVED: 'success',
  REJECTED: 'error',
};
export const EXPENSE_STATUS_OPTIONS: readonly Option<ExpenseStatus>[] = [
  { value: 'PENDING_APPROVAL', label: 'Pending approval' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'REJECTED', label: 'Rejected' },
];
export const PAID_FROM_OPTIONS: readonly Option<ExpensePaidFrom>[] = [
  { value: 'CASH_CUSTODY', label: 'Supervisor cash custody' },
  { value: 'COMPANY', label: 'Company (office / bank)' },
];
export const PAID_FROM_LABELS: Readonly<Record<ExpensePaidFrom, string>> = {
  CASH_CUSTODY: 'Supervisor cash custody',
  COMPANY: 'Company (office / bank)',
};
export const FUEL_EVENT_OPTIONS: readonly Option<FuelEventType>[] = [
  { value: 'PURCHASE', label: 'Purchase' },
  { value: 'ISSUE', label: 'Issue to machine' },
  { value: 'USAGE', label: 'Usage' },
];
export const APPROVAL_STATUS_TONES: Readonly<Record<ApprovalStatus, StatusTone>> = {
  PENDING: 'warning',
  APPROVED: 'success',
  REJECTED: 'error',
};
export const APPROVAL_STATUS_OPTIONS: readonly Option<ApprovalStatus>[] = [
  { value: 'PENDING', label: 'Pending' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'REJECTED', label: 'Rejected' },
];

/** Static currency list (code-defined) for currency selects; '' = the tenant's base currency. */
export const CURRENCY_OPTIONS: readonly Option[] = [
  { value: '', label: 'Tenant base currency' },
  ...SUPPORTED_CURRENCIES.map((c) => ({ value: c, label: c })),
];
export const CURRENCY_FILTER_OPTIONS: readonly Option[] = SUPPORTED_CURRENCIES.map((c) => ({
  value: c,
  label: c,
}));

/** Stable server error codes → what the user can do about them (shown with the server message). */
export const FINANCE_ERROR_HINTS: Readonly<Record<string, string>> = {
  SEGREGATION_OF_DUTIES:
    'The person who recorded or requested this cannot decide it. Ask another authorised colleague.',
  JOB_NOT_BILLABLE:
    'Only COMPLETED, billing-ready jobs can be invoiced. Resolve blocking exceptions or missing readings first.',
  JOB_ALREADY_INVOICED: 'The job is already on another non-voided invoice.',
  JOB_CUSTOMER_MISMATCH: 'Every job must belong to the selected customer.',
  DRAFT_STALE:
    'Job charges changed since drafting. Void this draft and create a new one from the current charges.',
  CURRENCY_MISMATCH: 'All amounts on one record must share a single currency.',
  NOT_CUSTODIAN: 'Only office cash staff may record custody for someone else.',
  INVOICE_NOT_DRAFT: 'Issued invoices are immutable; correct them by voiding.',
  INVOICE_ALREADY_VOIDED: 'This invoice is already voided.',
  INVOICE_NOT_OPEN: 'Payments can only be allocated to issued invoices.',
  OVER_ALLOCATION: 'Allocate no more than the invoice’s open amount.',
  ALLOCATION_EXCEEDS_PAYMENT: 'Allocations cannot exceed the payment amount.',
  ALLOCATION_MISMATCH: 'The invoice belongs to another customer or currency.',
  PAYMENT_REJECTED: 'A rejected payment cannot be allocated.',
  PAYMENT_ALREADY_DECIDED: 'Someone already decided this payment. Reload to see it.',
  HANDOVER_ALREADY_DECIDED: 'Someone already decided this handover. Reload to see it.',
  APPROVAL_ALREADY_DECIDED: 'Someone already decided this request. Reload to see it.',
  DUPLICATE_PAYMENT_REFERENCE: 'A payment with this method and reference already exists.',
  STAFF_NOT_LINKED: 'Your login is not linked to a staff record; pick the staff member explicitly.',
  STAFF_INACTIVE: 'The staff member is inactive.',
  CURRENCY_NOT_CONFIGURED: 'Choose a configured currency.',
  INVALID_PERIOD: 'The period end must not be before its start.',
  PERIOD_TOO_LONG: 'Choose a period of at most 366 days.',
  RECEIPT_REQUIRED: 'The EXPENSE_CAPTURE policy requires a receipt for this expense.',
  RECEIPT_NOT_FOUND: 'Upload the receipt again.',
  GPS_REQUIRED: 'The EXPENSE_CAPTURE policy requires an accurate GPS fix. Capture GPS and retry.',
  ATTRIBUTION_MISMATCH: 'The machine must match the job’s machine (or leave the machine empty).',
  CUSTODIAN_NOT_ALLOWED: 'A custodian applies only to expenses paid from cash custody.',
};

/** First 8 characters of an id, for records without a human label. */
export const shortId = (value: string): string => `${value.slice(0, 8)}…`;

/** "You" for the signed-in user (segregation of duties), else a short user id. */
export function actorLabel(userId: string | null, me: string | null): string {
  if (userId === null) return '—';
  return userId === me ? 'You' : shortId(userId);
}

/** Group rows by currency, keeping first-seen order. Amounts in different currencies never mix. */
export function groupByCurrency<T extends { currency: string }>(
  rows: readonly T[],
): [string, T[]][] {
  const out = new Map<string, T[]>();
  for (const r of rows) {
    const list = out.get(r.currency);
    if (list === undefined) out.set(r.currency, [r]);
    else list.push(r);
  }
  return [...out.entries()];
}
